import { render, screen, fireEvent, within } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterAll } from "vitest"
import i18n from "@/i18n"

// Mock wsClient BEFORE store imports it
vi.mock("@/transport/wsClient", () => ({
  wsClient: {
    send: vi.fn(),
    onStatus: vi.fn(() => vi.fn()),
    onMessage: vi.fn(() => vi.fn()),
    getStatus: vi.fn(() => "disconnected"),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

import { useGameStore } from "@/store/gameStore"
import { ActionBar } from "../ActionBar"
import type { ActionInfo, CombatAwareness, FleeStatus, TurnBudget } from "@/types/game"
import { wsClient } from "@/transport/wsClient"

const budget: TurnBudget = { actions: 1, bonus_actions: 1, movement_remaining: 30, reaction: 1 }

const fleeAction: ActionInfo = {
  name: "flee",
  description: "flee desc",
  params: [{ name: "destination_id", type: "string", required: true }],
  cost_type: "action",
}
const dodge: ActionInfo = { name: "dodge", description: "dodge desc", params: [], cost_type: "action" }
const endTurn: ActionInfo = { name: "end_turn", description: "end", params: [], cost_type: "free" }

const destinations = [
  { id: "forest", name: "Dark Forest", travel_seconds: 1800 },
  { id: "village", name: "Village", travel_seconds: 5400 },
]

function setCombat(flee: FleeStatus | null | undefined, actions: ActionInfo[]) {
  const awareness: CombatAwareness = {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Sword",
    self_weapon_damage: "1d8",
    nearby: [],
    round_number: 1,
    available_actions: actions,
    available_items: [],
    flee,
  }
  useGameStore.setState({ isMyTurn: true, waitingForAction: false, mode: "combat", awareness, budget })
}

const blocked = (reason_key: string | null, reason: string | null = "server reason"): FleeStatus => ({
  allowed: false,
  reason_key,
  reason,
  destinations,
})

const allowed: FleeStatus = { allowed: true, reason_key: null, reason: null, destinations }

function fleeButton() {
  return within(screen.getByTestId("flee-control")).getAllByRole("button")[0]
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
  useGameStore.setState({ isMyTurn: false, waitingForAction: false, mode: "peaceful", awareness: undefined, budget: undefined })
})

afterAll(async () => {
  await i18n.changeLanguage("en")
})

describe("Flee control — blocked", () => {
  it("is shown disabled with the ru reason when enemies are too close", async () => {
    await i18n.changeLanguage("ru")
    setCombat(blocked("enemies_too_close"), [dodge, endTurn])
    render(<ActionBar />)

    expect(fleeButton()).toBeDisabled()
    expect(fleeButton()).toHaveTextContent("Бегство")
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("Враги слишком близко, сбежать не выйдет")
  })

  it("is shown disabled with the en reason when enemies are too close", () => {
    setCombat(blocked("enemies_too_close"), [dodge, endTurn])
    render(<ActionBar />)

    expect(fleeButton()).toBeDisabled()
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("Enemies are too close to flee")
  })

  it("has its own text for no_exit in both languages", async () => {
    setCombat(blocked("no_exit"), [dodge, endTurn])
    const { unmount } = render(<ActionBar />)
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("There is nowhere to flee from here")
    unmount()

    await i18n.changeLanguage("ru")
    render(<ActionBar />)
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("Отсюда некуда бежать")
  })

  it("falls back to the server reason for an unknown reason_key", () => {
    setCombat(blocked("grappled", "You are held fast"), [dodge, endTurn])
    render(<ActionBar />)

    expect(screen.getByTestId("flee-reason")).toHaveTextContent("You are held fast")
  })

  it("names the missing Action when flee is allowed but the turn has no Action left", async () => {
    // The server drops `flee` from available_actions when the budget cannot pay for it.
    setCombat(allowed, [dodge, endTurn])
    useGameStore.setState({ budget: { ...budget, actions: 0 } })
    const { unmount } = render(<ActionBar />)
    expect(fleeButton()).toBeDisabled()
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("No Action left to flee")
    unmount()

    await i18n.changeLanguage("ru")
    render(<ActionBar />)
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("Не осталось действия, чтобы сбежать")
  })

  it("keeps the generic text when flee is allowed, the Action is there, but the action is not listed", () => {
    setCombat(allowed, [dodge, endTurn])
    render(<ActionBar />)
    expect(screen.getByTestId("flee-reason")).toHaveTextContent("Fleeing is not possible right now")
  })

  it("does not open a picker or send anything when clicked", () => {
    setCombat(blocked("enemies_too_close"), [dodge, endTurn])
    render(<ActionBar />)

    fireEvent.click(fleeButton())
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("is not rendered in peaceful mode (flee is null)", () => {
    setCombat(null, [dodge, endTurn])
    render(<ActionBar />)
    expect(screen.queryByTestId("flee-control")).not.toBeInTheDocument()
  })
})

describe("Flee control — destination picker", () => {
  it("lists destinations with travel time and nothing preselected", () => {
    setCombat(allowed, [dodge, fleeAction, endTurn])
    render(<ActionBar />)

    expect(fleeButton()).toBeEnabled()
    expect(screen.queryByTestId("flee-reason")).not.toBeInTheDocument()
    // Only one flee control, not an extra plain flee button
    expect(screen.getAllByRole("button", { name: /flee/i })).toHaveLength(1)

    fireEvent.click(fleeButton())
    expect(wsClient.send).not.toHaveBeenCalled()

    const items = within(screen.getByRole("menu")).getAllByRole("menuitem")
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent("Dark Forest")
    expect(items[0]).toHaveTextContent("30 min")
    expect(items[1]).toHaveTextContent("Village")
    expect(items[1]).toHaveTextContent("1 h 30 min")
    for (const item of items) {
      expect(item).not.toHaveAttribute("aria-checked", "true")
      expect(item).not.toHaveAttribute("aria-selected", "true")
    }
  })

  it("sends flee with the chosen destination_id", () => {
    setCombat(allowed, [dodge, fleeAction, endTurn])
    render(<ActionBar />)

    fireEvent.click(fleeButton())
    fireEvent.click(screen.getByRole("menuitem", { name: /Village/ }))

    expect(wsClient.send).toHaveBeenCalledTimes(1)
    expect(wsClient.send).toHaveBeenCalledWith({ type: "action", name: "flee", params: { destination_id: "village" } })
    expect(useGameStore.getState().waitingForAction).toBe(true)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("cancel closes the picker and sends nothing", () => {
    setCombat(allowed, [dodge, fleeAction, endTurn])
    render(<ActionBar />)

    fireEvent.click(fleeButton())
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
  })
})

describe("Flee control — after a successful flee", () => {
  it("drops combat controls and shows no spinner once the flee result arrives", () => {
    setCombat(allowed, [dodge, fleeAction, endTurn])
    const { rerender } = render(<ActionBar />)
    fireEvent.click(fleeButton())
    fireEvent.click(screen.getByRole("menuitem", { name: /Dark Forest/ }))

    useGameStore.getState().onActionResult({
      type: "action_result",
      actor: "p1",
      action: "flee",
      mode: "peaceful",
      awareness: { nearby: [], available_actions: [] } as unknown as CombatAwareness,
      events: [],
      budget,
      player: {
        player_id: "p1", name: "Hero", race: "human", char_class: "fighter", level: 1, experience: 0,
        level_up_available: false, xp_to_next_level: 300, alignment: "N", hp: 10, max_hp: 10, ac: 15, gold: 0,
        location_id: "camp", ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
        journey: {
          destination_id: "forest", destination_name: "Dark Forest", current_location_name: "Camp",
          next_location_name: "Dark Forest", remaining_route: ["Dark Forest"], next_arrival_seconds: 1800,
        },
      },
      location: { current_location: "Camp", current_location_id: "camp", description: "", region_id: "r", paths: [] },
    })
    rerender(<ActionBar />)

    expect(screen.queryByTestId("flee-control")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /dodge|end turn/i })).not.toBeInTheDocument()
    expect(document.querySelector(".animate-spin")).toBeNull()
  })
})
