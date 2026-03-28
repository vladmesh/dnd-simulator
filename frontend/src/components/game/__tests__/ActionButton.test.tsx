import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"

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
import type { ActionInfo, CombatAwareness, TurnBudget } from "@/types/game"
import { wsClient } from "@/transport/wsClient"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeAction(
  name: string,
  costType = "action",
  params: { name: string; type: string; required: boolean }[] = [],
): ActionInfo {
  return { name, description: `${name} desc`, params, cost_type: costType }
}

function setCombatState(
  actions: ActionInfo[],
  budget: TurnBudget,
  nearby: CombatAwareness["nearby"] = [],
) {
  const awareness: CombatAwareness = {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Sword",
    self_weapon_damage: "1d8",
    self_conditions: [],
    nearby,
    round_number: 1,
    available_actions: actions,
    available_items: [],
  }

  useGameStore.setState({
    isMyTurn: true,
    waitingForAction: false,
    mode: "combat",
    awareness,
    budget,
  })
}

const fullBudget: TurnBudget = {
  actions: 1,
  bonus_actions: 1,
  movement_remaining: 30,
  reaction: 1,
}

const depletedBudget: TurnBudget = {
  actions: 0,
  bonus_actions: 0,
  movement_remaining: 0,
  reaction: 0,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  useGameStore.setState({
    isMyTurn: false,
    waitingForAction: false,
    mode: "peaceful",
    awareness: undefined,
    budget: undefined,
  })
})

describe("ActionButton — simple actions", () => {
  it("simple action renders a plain button and sends on click", () => {
    setCombatState(
      [makeAction("dodge", "action"), makeAction("end_turn", "free")],
      fullBudget,
    )

    render(<ActionBar />)
    const btn = screen.getByTitle("dodge desc")
    expect(btn.tagName).toBe("BUTTON")
    fireEvent.click(btn)

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "dodge",
      params: undefined,
    })
  })

  it("wait action sends hours param", () => {
    setCombatState(
      [makeAction("wait", "free"), makeAction("end_turn", "free")],
      fullBudget,
    )

    render(<ActionBar />)
    fireEvent.click(screen.getByTitle("wait desc"))

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "wait",
      params: { hours: 1 },
    })
  })

  it("depleted budget disables button via data-depleted attr", () => {
    setCombatState(
      [makeAction("dodge", "action"), makeAction("end_turn", "free")],
      depletedBudget,
    )

    const { container } = render(<ActionBar />)
    const btn = container.querySelector('[data-cost-type="action"]') as HTMLElement
    expect(btn).toBeTruthy()
    expect(btn.hasAttribute("data-depleted")).toBe(true)
  })
})

describe("ActionButton — target selection", () => {
  it("renders target dropdown for attack with enemies", () => {
    setCombatState(
      [makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }])],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N" },
        { id: "goblin_2", description: "Goblin 2", distance_ft: 15, direction: "S" },
      ],
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    const dropdown = container.querySelector(".absolute.bottom-full")
    expect(dropdown).toBeTruthy()
  })

  it("renders directional dropdown for dash with direction param", () => {
    setCombatState(
      [
        makeAction("dash", "action", [{ name: "toward", type: "string", required: false }]),
        makeAction("end_turn", "free"),
      ],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N" }],
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("dash desc"))
    const dropdown = container.querySelector(".absolute.bottom-full")
    expect(dropdown).toBeTruthy()
  })
})

describe("SayAction", () => {
  it("clicking say opens text input", () => {
    setCombatState(
      [makeAction("say", "free"), makeAction("end_turn", "free")],
      fullBudget,
    )

    render(<ActionBar />)
    const sayBtn = screen.getByTitle("say desc")
    fireEvent.click(sayBtn)

    const input = screen.getByPlaceholderText(/say|сказать/i)
    expect(input).toBeTruthy()
  })

  it("typing text and pressing Enter sends say action with message", () => {
    setCombatState(
      [makeAction("say", "free"), makeAction("end_turn", "free")],
      fullBudget,
    )

    render(<ActionBar />)
    fireEvent.click(screen.getByTitle("say desc"))

    const input = screen.getByPlaceholderText(/say|сказать/i)
    fireEvent.change(input, { target: { value: "Hello there" } })
    fireEvent.keyDown(input, { key: "Enter" })

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "say",
      params: { text: "Hello there" },
    })
  })

  it("pressing Enter with empty text does NOT send", () => {
    setCombatState(
      [makeAction("say", "free"), makeAction("end_turn", "free")],
      fullBudget,
    )

    render(<ActionBar />)
    fireEvent.click(screen.getByTitle("say desc"))

    const input = screen.getByPlaceholderText(/say|сказать/i)
    fireEvent.keyDown(input, { key: "Enter" })

    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("Escape closes say input and clears text", () => {
    setCombatState(
      [makeAction("say", "free"), makeAction("end_turn", "free")],
      fullBudget,
    )

    render(<ActionBar />)
    fireEvent.click(screen.getByTitle("say desc"))

    const input = screen.getByPlaceholderText(/say|сказать/i)
    fireEvent.change(input, { target: { value: "partial text" } })
    fireEvent.keyDown(input, { key: "Escape" })

    // Input should be gone, say button should be back
    expect(screen.queryByPlaceholderText(/say|сказать/i)).toBeNull()
    expect(screen.getByTitle("say desc")).toBeTruthy()
  })

  it("clicking submit button sends say action", () => {
    setCombatState(
      [makeAction("say", "free"), makeAction("end_turn", "free")],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("say desc"))

    const input = screen.getByPlaceholderText(/say|сказать/i)
    fireEvent.change(input, { target: { value: "Greetings" } })

    // Find the submit button (↵)
    const submitBtn = container.querySelector("button")
    // The submit button with ↵ is next to the input
    const buttons = container.querySelectorAll("button")
    const enterBtn = Array.from(buttons).find((b) => b.textContent === "↵")
    expect(enterBtn).toBeTruthy()
    fireEvent.click(enterBtn!)

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "say",
      params: { text: "Greetings" },
    })
  })
})
