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
import { LootPanel } from "../LootPanel"
import type { CombatAwareness, CombatLootable, PeacefulAwareness, TurnBudget } from "@/types/game"
import { wsClient } from "@/transport/wsClient"

const fullBudget: TurnBudget = { actions: 1, bonus_actions: 1, movement_remaining: 30, reaction: 1 }

const adjacent: CombatLootable = {
  id: "goblin_corpse",
  name: "Goblin",
  description: "a dead goblin",
  in_reach: true,
  distance_ft: 5,
  reason_key: null,
  reason: null,
  loot_items: [{ id: "dagger_0", name: "Dagger", description: "Dagger", item_type: "weapon" }],
  loot_gold: 7,
}

const distant: CombatLootable = {
  id: "orc_corpse",
  name: "Orc",
  description: "a dead orc",
  in_reach: false,
  distance_ft: 20,
  reason_key: "too_far",
  reason: "server reason",
  loot_items: [],
  loot_gold: 12,
}

function setCombat(lootables: CombatLootable[], budget: TurnBudget = fullBudget, isMyTurn = true) {
  const awareness: CombatAwareness = {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Sword",
    self_weapon_damage: "1d8",
    nearby: [],
    round_number: 2,
    lootables,
  }
  useGameStore.setState({ isMyTurn, waitingForAction: false, mode: "combat", awareness, budget })
}

function takeButton(holderId: string) {
  return within(screen.getByTestId(`loot-${holderId}`)).getByRole("button")
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
  useGameStore.setState({ isMyTurn: false, waitingForAction: false, mode: "peaceful", awareness: undefined, budget: undefined })
})

afterAll(async () => {
  await i18n.changeLanguage("en")
})

describe("LootPanel — combat", () => {
  it("offers an adjacent corpse and sends take for it", () => {
    setCombat([adjacent])
    render(<LootPanel />)

    expect(screen.getByText("Goblin")).toBeInTheDocument()
    expect(screen.getAllByText("Dagger").length).toBeGreaterThan(0)
    const button = takeButton("goblin_corpse")
    expect(button).toBeEnabled()

    fireEvent.click(button)
    expect(wsClient.send).toHaveBeenCalledWith({ type: "action", name: "take", params: { target_id: "goblin_corpse" } })
    expect(useGameStore.getState().waitingForAction).toBe(true)
  })

  it("shows a distant corpse disabled with the reach reason", () => {
    setCombat([adjacent, distant])
    render(<LootPanel />)

    const button = takeButton("orc_corpse")
    expect(button).toBeDisabled()
    expect(within(screen.getByTestId("loot-orc_corpse")).getByTestId("loot-reason")).toHaveTextContent(
      "Too far (20 ft) — move next to it",
    )
    fireEvent.click(button)
    expect(wsClient.send).not.toHaveBeenCalled()
    expect(takeButton("goblin_corpse")).toBeEnabled()
  })

  it("shows the reach reason in Russian", async () => {
    await i18n.changeLanguage("ru")
    setCombat([distant])
    render(<LootPanel />)

    expect(screen.getByTestId("loot-reason")).toHaveTextContent("Слишком далеко (20 фт) — подойдите вплотную")
  })

  it("falls back to the server reason for an unknown reason key", () => {
    setCombat([{ ...distant, reason_key: "something_new" }])
    render(<LootPanel />)

    expect(screen.getByTestId("loot-reason")).toHaveTextContent("server reason")
  })

  it("disables taking once the Action is spent", () => {
    setCombat([adjacent], { ...fullBudget, actions: 0 })
    render(<LootPanel />)

    expect(takeButton("goblin_corpse")).toBeDisabled()
    expect(screen.getByTestId("loot-reason")).toHaveTextContent("No Action left this turn")
  })

  it("disables taking outside the player's turn", () => {
    setCombat([adjacent], fullBudget, false)
    render(<LootPanel />)

    expect(takeButton("goblin_corpse")).toBeDisabled()
  })

  it("renders nothing when no holder is at the fight", () => {
    setCombat([])
    const { container } = render(<LootPanel />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe("LootPanel — peaceful (unchanged)", () => {
  it("lists lootable nearby holders and takes without reach limits", () => {
    const awareness: PeacefulAwareness = {
      hour: 10,
      day: 1,
      month: 1,
      year: 1490,
      weather: {},
      location_name: "Cave",
      region_name: "Hills",
      nearby: [
        { id: "chest_1", description: "a chest", name: "Chest", lootable: true, loot_items: [], loot_gold: 5 },
        { id: "bob", description: "a villager", name: "Bob" },
      ],
    }
    useGameStore.setState({ isMyTurn: true, waitingForAction: false, mode: "peaceful", awareness, budget: undefined })
    render(<LootPanel />)

    expect(screen.queryByText("Bob")).not.toBeInTheDocument()
    expect(screen.queryByTestId("loot-reason")).not.toBeInTheDocument()
    fireEvent.click(takeButton("chest_1"))
    expect(wsClient.send).toHaveBeenCalledWith({ type: "action", name: "take", params: { target_id: "chest_1" } })
  })
})
