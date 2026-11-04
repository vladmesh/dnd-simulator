import { act, fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"

vi.mock("@/transport/apiClient", () => ({
  api: { player: {}, master: {}, health: vi.fn() },
}))

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
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness, ItemInfo, PlayerStatus } from "@/types/game"
import { InventoryPanel } from "../InventoryPanel"

const player: PlayerStatus = {
  player_id: "hero",
  name: "Hero",
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
  gold: 10,
  location_id: "camp",
  ability_scores: { str: 15, dex: 12, con: 14, int: 10, wis: 10, cha: 8 },
}

const potion: ItemInfo = {
  id: "potion-1", name: "Healing draught", type: "potion", description: "Restores health",
}

const combat: CombatAwareness = {
  self_hp: 20,
  self_max_hp: 20,
  self_ac: 15,
  self_speed: 30,
  self_weapon: "Fists",
  self_weapon_damage: "1",
  nearby: [],
  round_number: 1,
}

beforeEach(async () => {
  vi.clearAllMocks()
  useGameStore.setState(useGameStore.getInitialState(), true)
  await i18n.changeLanguage("en")
})

describe("InventoryPanel — remaining rendering and action branches", () => {
  it("waits for a player, then renders empty slots when optional collections are absent", () => {
    render(<InventoryPanel />)
    expect(screen.queryByRole("button", { name: "Inventory" })).not.toBeInTheDocument()

    act(() => useGameStore.getState().updatePlayer(player))

    expect(screen.getByRole("button", { name: "Inventory" })).toBeEnabled()
    for (const label of ["Weapon", "Armor", "Shield", "Head", "Feet", "Ring"]) {
      expect(screen.getByText(label)).toBeVisible()
    }
    expect(screen.queryByText("Bag")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Equip" })).not.toBeInTheDocument()
  })

  it("renders bag prices and non-equippable items, and collapses and reopens the inventory", () => {
    useGameStore.setState({
      player: {
        ...player,
        equipped: [],
        inventory: [
          { id: "stone", name: "Smooth stone", type: "misc", description: "", price: 0 },
          { id: "charm", name: "Loose charm", type: "accessory", description: "", price: null },
          { id: "map", name: "Old map", description: "", price: 12 },
        ],
      },
    })
    render(<InventoryPanel />)

    expect(screen.getByText("Bag")).toBeVisible()
    expect(screen.getByText("Smooth stone")).toBeVisible()
    expect(screen.getByText("0g")).toBeVisible()
    expect(screen.getByText("Loose charm")).toBeVisible()
    expect(screen.getByText("Old map")).toBeVisible()
    expect(screen.getByText("12g")).toBeVisible()
    expect(screen.queryByText("nullg")).not.toBeInTheDocument()
    expect(screen.getAllByRole("button")).toHaveLength(1)

    fireEvent.click(screen.getByRole("button", { name: "Inventory" }))
    expect(screen.queryByText("Bag")).not.toBeInTheDocument()
    expect(screen.queryByText("Smooth stone")).not.toBeInTheDocument()
    expect(screen.queryByText("Weapon")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Inventory" }))
    expect(screen.getByText("Smooth stone")).toBeVisible()
    expect(screen.getByText("Weapon")).toBeVisible()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("does not send an unsupported accessory slot or enter the waiting state", () => {
    useGameStore.setState({
      player: {
        ...player,
        inventory: [{ id: "amulet", name: "Amulet", type: "accessory", slot: "neck", description: "" }],
      },
      mode: "combat",
      isMyTurn: false,
    })
    render(<InventoryPanel />)

    const equip = screen.getByRole("button", { name: "Equip" })
    expect(screen.getByText("Amulet")).toBeVisible()
    expect(equip).toBeEnabled()
    fireEvent.click(equip)
    expect(wsClient.send).not.toHaveBeenCalled()
    expect(equip).toBeEnabled()
  })

  it.each([
    { type: "armor", slot: "armor", name: "Chain mail", action: "equip_armor", param: "armor_id" },
    { type: "shield", slot: "shield", name: "Buckler", action: "equip_shield", param: "shield_id" },
    { type: "accessory", slot: "head", name: "Circlet", action: "equip_head", param: "head_id" },
    { type: "accessory", slot: "feet", name: "Boots", action: "equip_feet", param: "feet_id" },
    { type: "accessory", slot: "ring", name: "Silver band", action: "equip_ring", param: "ring_id" },
  ])("sends $action with the correct item parameter and prevents duplicate requests", ({ type, slot, name, action, param }) => {
    useGameStore.setState({
      player: { ...player, inventory: [{ id: "item-1", name, type, slot, description: "" }] },
    })
    render(<InventoryPanel />)

    expect(screen.getByText(name)).toBeVisible()
    const equip = screen.getByRole("button", { name: "Equip" })
    fireEvent.click(equip)
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: action, params: { [param]: "item-1" },
    })
    expect(equip).toBeDisabled()
    fireEvent.click(equip)
    expect(wsClient.send).toHaveBeenCalledTimes(1)
  })

  it("sends the matching unequip action for each occupied equipment slot", () => {
    const slots = [
      { slot: "weapon", name: "Axe", action: "unequip" },
      { slot: "armor", name: "Leather vest", action: "unequip_armor" },
      { slot: "shield", name: "Tower shield", action: "unequip_shield" },
      { slot: "head", name: "Helm", action: "unequip_head" },
      { slot: "feet", name: "Greaves", action: "unequip_feet" },
      { slot: "ring", name: "Ruby ring", action: "unequip_ring" },
    ]
    useGameStore.setState({
      player: {
        ...player,
        equipped: slots.map(({ slot, name }) => ({ slot, name, item_id: slot, description: "" })),
        inventory: [],
      },
    })
    render(<InventoryPanel />)

    for (const [index, { name, action }] of slots.entries()) {
      fireEvent.click(screen.getByRole("button", { name }))
      expect(wsClient.send).toHaveBeenNthCalledWith(index + 1, { type: "action", name: action, params: undefined })
      for (const item of slots) {
        expect(screen.getByRole("button", { name: item.name })).toBeDisabled()
      }
      act(() => useGameStore.getState().setWaitingForAction(false))
    }
    expect(wsClient.send).toHaveBeenCalledTimes(slots.length)
  })

  it("locks all actions while using a potion, allows retry after an error, and renders the successful result", () => {
    const equipped = [{ slot: "weapon", item_id: "axe", name: "Handaxe", description: "" }]
    const shield: ItemInfo = { id: "shield", name: "Wooden shield", type: "shield", description: "" }
    useGameStore.setState({ player: { ...player, equipped, inventory: [potion, shield] } })
    render(<InventoryPanel />)

    const use = screen.getByRole("button", { name: "Use" })
    fireEvent.click(use)
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "use_item", params: { item_id: "potion-1" },
    })
    for (const name of ["Use", "Equip", "Handaxe"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled()
      fireEvent.click(screen.getByRole("button", { name }))
    }
    expect(wsClient.send).toHaveBeenCalledTimes(1)

    // Errors are displayed elsewhere; this panel only unlocks its controls.
    act(() => useGameStore.getState().onError({ type: "error", message: "Try again" }))
    for (const name of ["Use", "Equip", "Handaxe"]) {
      expect(screen.getByRole("button", { name })).toBeEnabled()
    }
    fireEvent.click(use)
    expect(wsClient.send).toHaveBeenNthCalledWith(2, {
      type: "action", name: "use_item", params: { item_id: "potion-1" },
    })

    act(() => useGameStore.getState().onActionResult({
      type: "action_result",
      actor: player.player_id,
      action: "use_item",
      mode: "peaceful",
      awareness: { hour: 12, day: 1, month: 1, year: 1, weather: {}, location_name: "Camp", region_name: "Valley", nearby: [] },
      events: [],
      player: { ...player, equipped, inventory: [shield] },
      location: { current_location: "Camp", current_location_id: "camp", description: "", region_id: "valley", paths: [] },
    }))
    expect(screen.queryByText("Healing draught")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Use" })).not.toBeInTheDocument()
    expect(screen.getByText("Wooden shield")).toBeVisible()
    expect(screen.getByRole("button", { name: "Equip" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Handaxe" })).toBeEnabled()
  })

  it("does not infer combat restrictions from missing awareness, action lists, or budget", () => {
    useGameStore.setState({
      player: {
        ...player,
        inventory: [{ id: "shield", name: "Buckler", type: "shield", description: "" }, potion],
      },
      mode: "combat",
      isMyTurn: true,
    })
    render(<InventoryPanel />)

    expect(screen.getByRole("button", { name: "Equip" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Use" })).toBeEnabled()

    act(() => useGameStore.setState({ awareness: combat }))
    expect(screen.getByRole("button", { name: "Equip" })).toBeEnabled()

    act(() => useGameStore.setState({
      awareness: { ...combat, available_actions: [{ name: "equip_shield", description: "", params: [], cost_type: "action" }] },
      budget: null,
    }))
    expect(screen.getByRole("button", { name: "Equip" })).toBeEnabled()
    expect(screen.queryByText("No Action left this turn")).not.toBeInTheDocument()
  })
})
