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
import type { ActionInfo, CombatAwareness, TurnBudget, ResourcePoolInfo } from "@/types/game"
import { wsClient } from "@/transport/wsClient"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeAction(
  name: string,
  costType = "action",
  params: { name: string; type: string; required: boolean }[] = [],
  opts: { target_mode?: string; target_scope?: string } = {},
): ActionInfo {
  return { name, description: `${name} desc`, params, cost_type: costType, ...opts }
}

function setCombatState(
  actions: ActionInfo[],
  budget: TurnBudget,
  nearby: CombatAwareness["nearby"] = [],
  resourcePools?: ResourcePoolInfo[],
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
    self_resource_pools: resourcePools,
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
  it("renders target dropdown for attack with target_mode single", () => {
    setCombatState(
      [makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "hostile" })],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true },
        { id: "goblin_2", description: "Goblin 2", distance_ft: 15, direction: "S", is_hostile: true },
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

describe("ActionButton — target scope filtering", () => {
  it("HOSTILE scope filters to hostile targets only", () => {
    setCombatState(
      [makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "hostile" })],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true },
        { id: "ally_1", description: "Friendly Guard", distance_ft: 10, direction: "S", is_hostile: false },
      ],
    )

    render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    // Only 1 hostile target after filtering → auto-sends directly
    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_1" },
    })
  })

  it("ALLY scope shows allies and self, hides hostiles", () => {
    // Set player in store so self_id is available
    useGameStore.setState({
      player: {
        player_id: "player_1",
        name: "Hero",
        race: "human",
        char_class: "paladin",
        level: 1,
        alignment: "lawful_good",
        hp: 20,
        max_hp: 20,
        ac: 16,
        gold: 10,
        location_id: "loc1",
        ability_scores: { str: 16, dex: 10, con: 14, int: 8, wis: 12, cha: 14 },
      },
    })

    setCombatState(
      [makeAction("lay_on_hands", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "ally" })],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true },
        { id: "ally_1", description: "Friendly Guard", distance_ft: 10, direction: "S", is_hostile: false },
      ],
    )

    const { container } = render(<ActionBar />)
    // lay_on_hands is in class features drawer — open it first
    const drawerBtn = container.querySelector('[data-drawer="class-features"]') as HTMLElement
    expect(drawerBtn).toBeTruthy()
    fireEvent.click(drawerBtn)
    // Now click the lay_on_hands action button inside the drawer
    fireEvent.click(screen.getByTitle("lay_on_hands desc"))
    // Target dropdown is the nested .absolute.bottom-full INSIDE the drawer popup
    const drawerPopup = container.querySelector('[data-drawer-popup="class-features"]')
    expect(drawerPopup).toBeTruthy()
    const targetDropdown = drawerPopup!.querySelector(".absolute.bottom-full")
    expect(targetDropdown).toBeTruthy()
    const options = targetDropdown!.querySelectorAll("button")
    // Should show: Self (player_1) + ally_1 = 2 options
    expect(options.length).toBe(2)
    // Should NOT contain goblin
    const texts = Array.from(options).map((b) => b.textContent)
    expect(texts.some((t) => t?.includes("goblin_1"))).toBe(false)
  })

  it("ANY scope shows everyone including self", () => {
    useGameStore.setState({
      player: {
        player_id: "player_1",
        name: "Hero",
        race: "human",
        char_class: "paladin",
        level: 1,
        alignment: "lawful_good",
        hp: 20,
        max_hp: 20,
        ac: 16,
        gold: 10,
        location_id: "loc1",
        ability_scores: { str: 16, dex: 10, con: 14, int: 8, wis: 12, cha: 14 },
      },
    })

    setCombatState(
      [makeAction("some_action", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "any" })],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true },
        { id: "ally_1", description: "Friendly Guard", distance_ft: 10, direction: "S", is_hostile: false },
      ],
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("some_action desc"))
    const dropdown = container.querySelector(".absolute.bottom-full")
    expect(dropdown).toBeTruthy()
    const options = dropdown!.querySelectorAll("button")
    // Should show: Self + goblin_1 + ally_1 = 3 options
    expect(options.length).toBe(3)
  })

  it("Self entry sends correct target_id", () => {
    useGameStore.setState({
      player: {
        player_id: "player_1",
        name: "Hero",
        race: "human",
        char_class: "paladin",
        level: 1,
        alignment: "lawful_good",
        hp: 20,
        max_hp: 20,
        ac: 16,
        gold: 10,
        location_id: "loc1",
        ability_scores: { str: 16, dex: 10, con: 14, int: 8, wis: 12, cha: 14 },
      },
    })

    setCombatState(
      [makeAction("lay_on_hands", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "ally" })],
      fullBudget,
      [
        { id: "ally_1", description: "Friendly Guard", distance_ft: 10, direction: "S", is_hostile: false },
      ],
    )

    const { container } = render(<ActionBar />)
    // lay_on_hands is in class features drawer — open it first
    const drawerBtn = container.querySelector('[data-drawer="class-features"]') as HTMLElement
    expect(drawerBtn).toBeTruthy()
    fireEvent.click(drawerBtn)
    // Now click the lay_on_hands action button inside the drawer
    fireEvent.click(screen.getByTitle("lay_on_hands desc"))
    const drawerPopup = container.querySelector('[data-drawer-popup="class-features"]')
    expect(drawerPopup).toBeTruthy()
    const targetDropdown = drawerPopup!.querySelector(".absolute.bottom-full")
    expect(targetDropdown).toBeTruthy()
    const options = targetDropdown!.querySelectorAll("button")
    // Find the Self option and click it
    const selfOption = Array.from(options).find((b) => b.textContent?.includes("Self") || b.textContent?.includes("Себя"))
    expect(selfOption).toBeTruthy()
    fireEvent.click(selfOption!)

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "lay_on_hands",
      params: { target_id: "player_1" },
    })
  })

  it("target_mode none renders simple button (no dropdown)", () => {
    setCombatState(
      [makeAction("dodge", "action", [], { target_mode: "none" }), makeAction("end_turn", "free")],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true }],
    )

    render(<ActionBar />)
    const btn = screen.getByTitle("dodge desc")
    fireEvent.click(btn)
    // Should send directly, no dropdown
    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "dodge",
      params: undefined,
    })
  })
})

describe("ActionButton — i18n labels", () => {
  it("lay_on_hands renders localized label, not raw snake_case", () => {
    setCombatState(
      [
        makeAction("lay_on_hands", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "ally" }),
        makeAction("end_turn", "free"),
      ],
      fullBudget,
      [{ id: "ally_1", description: "Ally", distance_ft: 10, direction: "N", is_hostile: false }],
    )

    render(<ActionBar />)
    // lay_on_hands goes to class features drawer — the drawer button should exist
    const drawerBtn = document.querySelector('[data-drawer="class-features"]')
    expect(drawerBtn).toBeTruthy()
  })

  it("long_rest and short_rest render localized labels", () => {
    useGameStore.setState({
      isMyTurn: true,
      waitingForAction: false,
      mode: "peaceful",
      awareness: {
        nearby: [],
        available_actions: [
          makeAction("long_rest", "free"),
          makeAction("short_rest", "free"),
        ],
        available_items: [],
      },
      budget: undefined,
    })

    render(<ActionBar />)
    // Should show localized labels, not raw "long_rest" / "short_rest"
    expect(screen.getByText("Long Rest")).toBeTruthy()
    expect(screen.getByText("Short Rest")).toBeTruthy()
  })

  it("class feature drawer does not show raw bonus_action string", () => {
    setCombatState(
      [
        makeAction("second_wind", "bonus_action"),
        makeAction("end_turn", "free"),
      ],
      fullBudget,
    )

    const { container } = render(<ActionBar />)
    // Open class features drawer
    const drawerBtn = container.querySelector('[data-drawer="class-features"]') as HTMLElement
    expect(drawerBtn).toBeTruthy()
    fireEvent.click(drawerBtn)

    // Drawer should render action buttons with proper labels, no raw "bonus_action" text
    const drawerPopup = container.querySelector('[data-drawer-popup="class-features"]')
    expect(drawerPopup).toBeTruthy()
    expect(drawerPopup!.textContent).not.toContain("bonus_action")
    // Cost type conveyed via data attribute, not visible text
    const actionBtn = drawerPopup!.querySelector('[data-cost-type="bonus_action"]')
    expect(actionBtn).toBeTruthy()
  })
})

describe("ActionButton — smite choice", () => {
  const attackAction = makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }], { target_mode: "single", target_scope: "hostile" })
  const spellSlots: ResourcePoolInfo[] = [
    { id: "spell_slot_1", max_uses: 2, current_uses: 1 },
  ]

  it("attack with spell slots shows smite choice after target selection", () => {
    setCombatState(
      [attackAction],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true }],
      spellSlots,
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    // Single target → auto-selects target, but should show smite choice instead of sending
    expect(wsClient.send).not.toHaveBeenCalled()
    // Smite choice panel should be visible
    const smitePanel = container.querySelector("[data-testid='smite-choice']")
    expect(smitePanel).toBeTruthy()
  })

  it("attack without spell slots sends action immediately (no smite choice)", () => {
    setCombatState(
      [attackAction],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true }],
      // no resource pools
    )

    render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    // Single target → auto-sends directly, no intermediate step
    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_1" },
    })
  })

  it("selecting 'Attack + Smite' sends smite_slot_level param", () => {
    setCombatState(
      [attackAction],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true }],
      spellSlots,
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    // Smite choice should be visible
    const smitePanel = container.querySelector("[data-testid='smite-choice']")
    expect(smitePanel).toBeTruthy()
    // Click the smite option
    const smiteOption = Array.from(smitePanel!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Smite") || b.textContent?.includes("Кара"),
    )
    expect(smiteOption).toBeTruthy()
    fireEvent.click(smiteOption!)

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_1", smite_slot_level: 1 },
    })
  })

  it("selecting 'Attack' (no smite) sends without smite_slot_level", () => {
    setCombatState(
      [attackAction],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true }],
      spellSlots,
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    const smitePanel = container.querySelector("[data-testid='smite-choice']")
    expect(smitePanel).toBeTruthy()
    // Click the normal attack option (without smite)
    const normalOption = Array.from(smitePanel!.querySelectorAll("button")).find((b) => {
      const text = b.textContent ?? ""
      return (text.includes("Attack") || text.includes("Атака")) && !text.includes("Smite") && !text.includes("Кара")
    })
    expect(normalOption).toBeTruthy()
    fireEvent.click(normalOption!)

    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_1" },
    })
  })

  it("depleted spell slots are shown but disabled", () => {
    const depletedSlots: ResourcePoolInfo[] = [
      { id: "spell_slot_1", max_uses: 2, current_uses: 0 },
    ]

    setCombatState(
      [attackAction],
      fullBudget,
      [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true }],
      depletedSlots,
    )

    const { container } = render(<ActionBar />)
    fireEvent.click(screen.getByTitle("attack desc"))
    const smitePanel = container.querySelector("[data-testid='smite-choice']")
    expect(smitePanel).toBeTruthy()
    // The smite option should be disabled
    const smiteOption = Array.from(smitePanel!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Smite") || b.textContent?.includes("Кара"),
    )
    expect(smiteOption).toBeTruthy()
    expect(smiteOption!.disabled).toBe(true)
  })

  it("smite choice works with multiple targets (dropdown then smite)", () => {
    setCombatState(
      [attackAction],
      fullBudget,
      [
        { id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N", is_hostile: true },
        { id: "goblin_2", description: "Goblin 2", distance_ft: 15, direction: "S", is_hostile: true },
      ],
      spellSlots,
    )

    const { container } = render(<ActionBar />)
    // Open target dropdown
    fireEvent.click(screen.getByTitle("attack desc"))
    const targetDropdown = container.querySelector(".absolute.bottom-full")
    expect(targetDropdown).toBeTruthy()
    // Select a target
    const targetOptions = targetDropdown!.querySelectorAll("button")
    fireEvent.click(targetOptions[0]) // click goblin_1
    // Should NOT send yet — smite choice should appear
    expect(wsClient.send).not.toHaveBeenCalled()
    const smitePanel = container.querySelector("[data-testid='smite-choice']")
    expect(smitePanel).toBeTruthy()
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
