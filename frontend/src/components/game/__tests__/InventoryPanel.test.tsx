import { render, screen, within, fireEvent } from "@testing-library/react"
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
import { InventoryPanel } from "../InventoryPanel"
import type { ActionInfo, BlockedAction, CombatAwareness, TurnBudget } from "@/types/game"
import { wsClient } from "@/transport/wsClient"

const fullBudget: TurnBudget = { actions: 1, bonus_actions: 1, movement_remaining: 30, reaction: 1 }
const spentBudget: TurnBudget = { actions: 0, bonus_actions: 1, movement_remaining: 30, reaction: 1 }

const player = {
  player_id: "p1",
  name: "Hero",
  equipped: [{ slot: "ring", item_id: "ring_0", name: "Ring of Warmth", description: "a ring" }],
  inventory: [
    { id: "chain_0", name: "Chain Mail", type: "armor", description: "heavy armor" },
    { id: "sword_0", name: "Longsword", type: "weapon", description: "a sword" },
    { id: "shield_0", name: "Shield", type: "shield", description: "+2 AC" },
  ],
}

const equipWeapon: ActionInfo = { name: "equip", description: "", cost_type: "free", params: [] }
const equipShield: ActionInfo = { name: "equip_shield", description: "", cost_type: "action", params: [] }
const wrongMode = (name: string): BlockedAction => ({ name, reason_key: "WRONG_MODE", reason: "server: not in combat" })

function setCombat({
  available = [equipWeapon, equipShield],
  blocked = [wrongMode("equip_armor"), wrongMode("unequip_ring")],
  budget = fullBudget,
  isMyTurn = true,
}: { available?: ActionInfo[]; blocked?: BlockedAction[]; budget?: TurnBudget; isMyTurn?: boolean } = {}) {
  const awareness: CombatAwareness = {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Fists",
    self_weapon_damage: "1",
    nearby: [],
    round_number: 1,
    available_actions: available,
    blocked_actions: blocked,
  }
  useGameStore.setState({ player, mode: "combat", awareness, budget, isMyTurn, waitingForAction: false } as never)
}

function equipButton(itemId: string) {
  return within(screen.getByTestId(`bag-${itemId}`)).getByRole("button") as HTMLButtonElement
}

function reasonFor(itemId: string) {
  return within(screen.getByTestId(`bag-${itemId}`)).queryByTestId("equip-reason")
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
  useGameStore.setState({ mode: "peaceful", awareness: undefined, budget: undefined, isMyTurn: false, waitingForAction: false })
})

afterAll(async () => {
  await i18n.changeLanguage("en")
})

describe("InventoryPanel — equip controls in combat", () => {
  it("disables armor equip with a human English reason", () => {
    setCombat()
    render(<InventoryPanel />)

    const button = equipButton("chain_0")
    expect(button.disabled).toBe(true)
    expect(button.title).toBe("Can't be changed in combat")
    expect(reasonFor("chain_0")?.textContent).toBe("Can't be changed in combat")
    expect(screen.queryByText(/equip_armor/)).toBeNull()
  })

  it("disables armor equip with a human Russian reason", async () => {
    await i18n.changeLanguage("ru")
    setCombat()
    render(<InventoryPanel />)

    expect(equipButton("chain_0").disabled).toBe(true)
    expect(reasonFor("chain_0")?.textContent).toBe("В бою это не сменить")
  })

  it("keeps weapon equip available and sends it", () => {
    setCombat()
    render(<InventoryPanel />)

    const button = equipButton("sword_0")
    expect(button.disabled).toBe(false)
    expect(reasonFor("sword_0")).toBeNull()
    fireEvent.click(button)
    expect(wsClient.send).toHaveBeenCalledWith({ type: "action", name: "equip", params: { weapon_id: "sword_0" } })
  })

  it("disables an equipped accessory's unequip with the reason", () => {
    setCombat()
    render(<InventoryPanel />)

    const unequip = screen.getByTestId("unequip-ring") as HTMLButtonElement
    expect(unequip.disabled).toBe(true)
    expect(unequip.title).toBe("Can't be changed in combat")
  })

  it("disables shield equip once the Action is spent (server block)", () => {
    setCombat({
      available: [equipWeapon],
      blocked: [
        wrongMode("equip_armor"),
        { name: "equip_shield", reason_key: "INSUFFICIENT_BUDGET", reason: "Insufficient budget for 'equip_shield'" },
      ],
      budget: spentBudget,
    })
    render(<InventoryPanel />)

    expect(equipButton("shield_0").disabled).toBe(true)
    expect(reasonFor("shield_0")?.textContent).toBe("No Action left this turn")
    expect(equipButton("sword_0").disabled).toBe(false)
  })

  it("disables shield equip from the local budget when the Action is spent after the awareness", () => {
    setCombat({ budget: spentBudget })
    render(<InventoryPanel />)

    expect(equipButton("shield_0").disabled).toBe(true)
    expect(reasonFor("shield_0")?.textContent).toBe("No Action left this turn")
  })

  it("falls back to the server's localised reason for an unknown key", () => {
    setCombat({ blocked: [{ name: "equip_armor", reason_key: "SOMETHING_NEW", reason: "Server says no" }] })
    render(<InventoryPanel />)

    expect(reasonFor("chain_0")?.textContent).toBe("Server says no")
  })

  it("asks to wait for the turn outside the player's turn, but keeps the mode reason for armor", () => {
    setCombat({ isMyTurn: false })
    render(<InventoryPanel />)

    expect(equipButton("sword_0").disabled).toBe(true)
    expect(reasonFor("sword_0")?.textContent).toBe("Wait for your turn")
    expect(reasonFor("chain_0")?.textContent).toBe("Can't be changed in combat")
  })
})

describe("InventoryPanel — out of combat", () => {
  it("enables every equip and unequip control", () => {
    useGameStore.setState({ player, mode: "peaceful", isMyTurn: true } as never)
    render(<InventoryPanel />)

    for (const id of ["chain_0", "sword_0", "shield_0"]) {
      expect(equipButton(id).disabled).toBe(false)
      expect(reasonFor(id)).toBeNull()
    }
    expect((screen.getByTestId("unequip-ring") as HTMLButtonElement).disabled).toBe(false)
  })
})

describe("InventoryPanel — real turn → action_result flow through the store", () => {
  // Shapes mirror the server payloads: the turn snapshot and every action-result snapshot
  // carry the same authoritative `blocked_actions` (backend test_blocked_actions_snapshots).
  const statusPlayer = {
    ...player,
    race: "human",
    char_class: "fighter",
    level: 1,
    experience: 0,
    level_up_available: false,
    xp_to_next_level: 300,
    alignment: "N",
    hp: 20,
    max_hp: 20,
    ac: 15,
    gold: 0,
    location_id: "arena",
    ability_scores: { str: 15, dex: 12, con: 14, int: 10, wis: 10, cha: 8 },
  }
  const location = { current_location: "Arena", current_location_id: "arena", description: "", region_id: "r", paths: [] }
  const combatAwareness = (blocked: BlockedAction[], available: ActionInfo[]): CombatAwareness => ({
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Fists",
    self_weapon_damage: "1",
    nearby: [],
    round_number: 1,
    available_actions: available,
    blocked_actions: blocked,
  })

  function turn() {
    useGameStore.getState().onTurn({
      type: "turn",
      mode: "combat",
      awareness: combatAwareness([wrongMode("equip_armor")], [equipWeapon, equipShield]),
      events: [],
      budget: fullBudget,
      player: statusPlayer,
      location,
    } as never)
  }

  function actionResult(actor: string, action: string) {
    // Action-result snapshots are built outside the turn loop and list no available actions.
    useGameStore.getState().onActionResult({
      type: "action_result",
      actor,
      action,
      mode: "combat",
      awareness: combatAwareness([wrongMode("equip_armor")], []),
      events: [],
      player: statusPlayer,
      location,
    } as never)
  }

  it("keeps armor equip disabled with its reason after the player's end_turn result", () => {
    turn()
    actionResult("p1", "end_turn")
    render(<InventoryPanel />)

    expect(equipButton("chain_0").disabled).toBe(true)
    expect(reasonFor("chain_0")?.textContent).toBe("Can't be changed in combat")
  })

  it("keeps armor equip disabled with its reason after an NPC action result", async () => {
    await i18n.changeLanguage("ru")
    turn()
    actionResult("goblin", "attack")
    render(<InventoryPanel />)

    expect(equipButton("chain_0").disabled).toBe(true)
    expect(reasonFor("chain_0")?.textContent).toBe("В бою это не сменить")
  })
})
