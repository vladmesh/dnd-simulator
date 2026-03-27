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

const depletedActionsBudget: TurnBudget = {
  actions: 0,
  bonus_actions: 1,
  movement_remaining: 30,
  reaction: 1,
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

describe("ActionBar — cost-type styling", () => {
  it("renders core combat buttons with data-cost-type attribute", () => {
    setCombatState(
      [
        makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
        makeAction("dodge", "action"),
        makeAction("dash", "action"),
        makeAction("disengage", "action"),
        makeAction("end_turn", "free"),
      ],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    const buttons = container.querySelectorAll("[data-cost-type]")
    expect(buttons.length).toBeGreaterThan(0)

    const costTypes = Array.from(buttons).map((b) => b.getAttribute("data-cost-type"))
    expect(costTypes).toContain("action")
  })

  it("end_turn always renders last", () => {
    setCombatState(
      [
        makeAction("end_turn", "free"),
        makeAction("dodge", "action"),
        makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
      ],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    const allButtons = container.querySelectorAll("button")
    const lastButton = allButtons[allButtons.length - 1]
    expect(lastButton.textContent).toMatch(/end.turn/i)
  })

  it("shows budget display when budget exists", () => {
    setCombatState([makeAction("dodge", "action")], fullBudget)

    const { container } = render(<ActionBar />)
    // BudgetDisplay renders resource counters with icons
    const budgetSection = container.querySelector(".flex.gap-3")
    expect(budgetSection).toBeTruthy()
  })

  it("bonus_action buttons have distinct visual styling", () => {
    setCombatState(
      [
        makeAction("second_wind", "bonus_action"),
        makeAction("dodge", "action"),
        makeAction("end_turn", "free"),
      ],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    const bonusButtons = container.querySelectorAll('[data-cost-type="bonus_action"]')
    expect(bonusButtons.length).toBeGreaterThan(0)
  })

  it("depleted action-cost buttons show depleted styling", () => {
    setCombatState(
      [makeAction("dodge", "action"), makeAction("end_turn", "free")],
      depletedActionsBudget,
    )

    const { container } = render(<ActionBar />)
    const actionButtons = container.querySelectorAll('[data-cost-type="action"]')
    expect(actionButtons.length).toBeGreaterThan(0)
    const btn = actionButtons[0] as HTMLElement
    expect(btn.hasAttribute("data-depleted")).toBe(true)
  })

  it("attack with single enemy sends action directly", () => {
    setCombatState(
      [makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }])],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N" }],
    )

    render(<ActionBar />)
    const attackButton = screen.getByTitle("attack desc")
    attackButton.click()
    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_1" },
    })
  })

  it("attack with multiple enemies shows target dropdown", () => {
    setCombatState(
      [makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }])],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N" },
        { id: "goblin_2", description: "Goblin 2", distance_ft: 15, direction: "S" },
      ],
    )

    const { container } = render(<ActionBar />)
    const attackButton = screen.getByTitle("attack desc")
    fireEvent.click(attackButton)
    // Dropdown should now be visible with target options
    const dropdown = container.querySelector(".absolute.bottom-full")
    expect(dropdown).toBeTruthy()
    const options = dropdown!.querySelectorAll("button")
    expect(options.length).toBe(2)
  })
})
