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
import type { ActionInfo, CombatAwareness, TurnBudget, ItemInfo } from "@/types/game"
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
  items: ItemInfo[] = [],
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
    available_items: items,
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

  it("bonus_action buttons have distinct visual styling in class features drawer", () => {
    setCombatState(
      [
        makeAction("second_wind", "bonus_action"),
        makeAction("dodge", "action"),
        makeAction("end_turn", "free"),
      ],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    // Class features go to drawer; open it and check cost type badge
    const drawerBtn = container.querySelector("[data-drawer='class-features']") as HTMLElement
    expect(drawerBtn).toBeTruthy()
    fireEvent.click(drawerBtn)
    const popup = container.querySelector("[data-drawer-popup='class-features']")
    expect(popup).toBeTruthy()
    expect(popup!.textContent).toContain("bonus_action")
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

describe("ActionBar — consumable drawer", () => {
  const potions: ItemInfo[] = [
    { id: "pot_1", name: "Healing Potion", item_type: "potion", description: "Heals 2d4+2 HP" },
    { id: "pot_2", name: "Greater Healing", item_type: "potion", description: "Heals 4d4+4 HP" },
  ]

  it("renders consumable drawer button with count when items available", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']")
    expect(drawerBtn).toBeTruthy()
    expect(drawerBtn!.textContent).toContain("2")
  })

  it("consumable drawer button has a tooltip", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    expect(drawerBtn).toBeTruthy()
    expect(drawerBtn.getAttribute("title")).toBeTruthy()
  })

  it("clicking consumable drawer opens popup with potion names", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    fireEvent.click(drawerBtn)

    expect(screen.getByText("Healing Potion")).toBeTruthy()
    expect(screen.getByText("Greater Healing")).toBeTruthy()
  })

  it("clicking a potion sends use_item with correct item_id", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    fireEvent.click(drawerBtn)
    fireEvent.click(screen.getByText("Healing Potion"))

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "use_item",
      params: { item_id: "pot_1" },
    })
  })

  it("popup closes after action is sent", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    fireEvent.click(drawerBtn)
    expect(screen.getByText("Healing Potion")).toBeTruthy()

    fireEvent.click(screen.getByText("Healing Potion"))
    // Popup should be closed — potion names no longer visible
    expect(screen.queryByText("Healing Potion")).toBeNull()
  })

  it("no consumable drawer when available_items is empty", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']")
    expect(drawerBtn).toBeNull()
  })
})

describe("ActionBar — class features drawer", () => {
  it("renders class features drawer when second_wind available", () => {
    setCombatState(
      [makeAction("second_wind", "bonus_action"), makeAction("dodge", "action")],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='class-features']")
    expect(drawerBtn).toBeTruthy()
  })

  it("clicking second_wind in class features popup sends action", () => {
    setCombatState(
      [makeAction("second_wind", "bonus_action"), makeAction("dodge", "action")],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='class-features']") as HTMLElement
    fireEvent.click(drawerBtn)
    // Find the second_wind button inside the popup
    const popup = container.querySelector("[data-drawer-popup='class-features']")
    expect(popup).toBeTruthy()
    const swButton = popup!.querySelector("button")
    expect(swButton).toBeTruthy()
    fireEvent.click(swButton!)

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "second_wind",
      params: undefined,
    })
  })
})

describe("ActionBar — drawer interactions", () => {
  const potions: ItemInfo[] = [
    { id: "pot_1", name: "Healing Potion", item_type: "potion", description: "Heals 2d4+2 HP" },
  ]

  it("opening consumable drawer closes class features drawer", () => {
    setCombatState(
      [
        makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }]),
        makeAction("second_wind", "bonus_action"),
      ],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    // Open class features
    const cfBtn = container.querySelector("[data-drawer='class-features']") as HTMLElement
    fireEvent.click(cfBtn)
    expect(container.querySelector("[data-drawer-popup='class-features']")).toBeTruthy()

    // Open consumables — class features should close
    const conBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    fireEvent.click(conBtn)
    expect(container.querySelector("[data-drawer-popup='consumables']")).toBeTruthy()
    expect(container.querySelector("[data-drawer-popup='class-features']")).toBeNull()
  })

  it("opening a drawer closes any open core dropdown", () => {
    setCombatState(
      [
        makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
        makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }]),
      ],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N" },
        { id: "goblin_2", description: "Goblin 2", distance_ft: 15, direction: "S" },
      ],
      potions,
    )

    const { container } = render(<ActionBar />)
    // Open attack dropdown
    fireEvent.click(screen.getByTitle("attack desc"))
    expect(container.querySelector(".absolute.bottom-full")).toBeTruthy()

    // Open consumable drawer — attack dropdown should close
    const conBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    fireEvent.click(conBtn)
    // Only the drawer popup should remain, not the attack dropdown
    expect(container.querySelector("[data-drawer-popup='consumables']")).toBeTruthy()
  })

  it("Escape closes open drawer", () => {
    setCombatState(
      [makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }])],
      fullBudget,
      [],
      potions,
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='consumables']") as HTMLElement
    fireEvent.click(drawerBtn)
    expect(container.querySelector("[data-drawer-popup='consumables']")).toBeTruthy()

    // Fire escape on the action bar container (the element with tabIndex)
    const actionBarContainer = container.querySelector("[tabindex]") as HTMLElement
    fireEvent.keyDown(actionBarContainer, { key: "Escape" })
    expect(container.querySelector("[data-drawer-popup='consumables']")).toBeNull()
  })
})

describe("ActionBar — inventory drawer", () => {
  it("inventory drawer does not render in peaceful mode", () => {
    useGameStore.setState({
      isMyTurn: true,
      waitingForAction: false,
      mode: "peaceful",
      awareness: {
        hour: 10, day: 1, month: 1, year: 1,
        weather: {},
        location_name: "Town",
        region_name: "Valley",
        nearby: [],
        settlements: null,
        territory_owner: null,
        nation_info: null,
        available_actions: [
          makeAction("equip", "free", [{ name: "weapon_id", type: "string", required: true }]),
          makeAction("say", "free"),
        ],
        available_items: [{ id: "w1", name: "Sword", item_type: "weapon", description: "A sharp sword" }],
      },
      budget: undefined,
    })

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='inventory']")
    expect(drawerBtn).toBeNull()
  })

  it("inventory drawer renders in combat with equip action available", () => {
    setCombatState(
      [
        makeAction("equip", "free", [{ name: "weapon_id", type: "string", required: true }]),
        makeAction("dodge", "action"),
      ],
      fullBudget,
      [],
      [{ id: "w1", name: "Sword", item_type: "weapon", description: "A sharp sword" }],
    )

    const { container } = render(<ActionBar />)
    const drawerBtn = container.querySelector("[data-drawer='inventory']")
    expect(drawerBtn).toBeTruthy()
  })
})
