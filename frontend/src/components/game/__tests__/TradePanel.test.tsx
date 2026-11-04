import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"
import type { CombatAwareness, ItemInfo, MerchantInfo, PeacefulAwareness, PlayerStatus } from "@/types/game"

// Trading uses WebSocket actions, not REST; keep both transports off the network.
vi.mock("@/transport/apiClient", () => ({ api: {} }))
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
import { TradePanel } from "../TradePanel"

const potion: ItemInfo = { id: "potion", name: "Healing potion", description: "Restores health", price: 15 }
const gem: ItemInfo = { id: "gem", name: "Ruby", description: "A red gem", price: 10 }
const merchant: MerchantInfo = { id: "alchemist", name: "Mira", gold: 100, items: [potion] }
const player: PlayerStatus = {
  player_id: "hero",
  name: "Hero",
  race: "human",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "neutral",
  hp: 10,
  max_hp: 10,
  ac: 12,
  gold: 10,
  location_id: "market",
  ability_scores: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
  inventory: [],
}

function awareness(merchants?: MerchantInfo[]): PeacefulAwareness {
  return {
    hour: 12,
    day: 1,
    month: 1,
    year: 1490,
    weather: {},
    location_name: "Market",
    region_name: "Town",
    nearby: [],
    ...(merchants === undefined ? {} : { merchants }),
  }
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
  useGameStore.setState(useGameStore.getInitialState())
})

afterAll(async () => {
  await i18n.changeLanguage("en")
})

describe("TradePanel — branches beyond ItemDetails' priced-buy and tooltip tests", () => {
  it("stays hidden before awareness loads and when awareness has no merchants", () => {
    render(<TradePanel />)
    expect(screen.queryByRole("button", { name: "Trade" })).not.toBeInTheDocument()

    for (const next of [awareness(), awareness([])]) {
      act(() => useGameStore.setState({ awareness: next }))
      expect(screen.queryByRole("button", { name: "Trade" })).not.toBeInTheDocument()
    }

    const combat: CombatAwareness = {
      self_hp: 10, self_max_hp: 10, self_ac: 12, self_speed: 30,
      self_weapon: "Sword", self_weapon_damage: "1d8", nearby: [], round_number: 1,
    }
    act(() => useGameStore.setState({ mode: "combat", awareness: combat }))
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("lists multiple merchants expanded initially and toggles their visibility", () => {
    useGameStore.setState({
      player,
      awareness: awareness([merchant, { id: "smith", name: "Oren", gold: 250, items: [] }]),
    })
    render(<TradePanel />)

    expect(screen.getByText("Mira")).toBeVisible()
    expect(screen.getByText("100g")).toBeVisible()
    expect(screen.getByText("Oren")).toBeVisible()
    expect(screen.getByText("250g")).toBeVisible()
    expect(screen.getByText("Healing potion")).toBeVisible()
    expect(screen.getByText("15g")).toBeVisible()

    fireEvent.click(screen.getByRole("button", { name: "Trade" }))
    expect(screen.queryByText("Mira")).not.toBeInTheDocument()
    expect(screen.queryByText("Oren")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Buy" })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Trade" }))
    expect(screen.getByText("Mira")).toBeVisible()
    expect(screen.getByText("Oren")).toBeVisible()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("omits empty buy and sell sections and excludes items without positive prices", () => {
    const unsellable: ItemInfo[] = [
      { id: "key", name: "Key", description: "Opens a door" },
      { id: "map", name: "Map", description: "A map", price: null },
      { id: "rock", name: "Rock", description: "A rock", price: 0 },
      { id: "debt", name: "Debt", description: "An IOU", price: -1 },
    ]
    useGameStore.setState({
      player: { ...player, inventory: unsellable },
      awareness: awareness([{ ...merchant, items: [] }]),
    })
    render(<TradePanel />)

    expect(screen.getByText("Mira")).toBeVisible()
    expect(screen.queryByText("Buy")).not.toBeInTheDocument()
    expect(screen.queryByText("Sell")).not.toBeInTheDocument()
    for (const item of unsellable) {
      expect(screen.queryByText(item.name)).not.toBeInTheDocument()
    }
    expect(screen.getAllByRole("button")).toHaveLength(1)
  })

  it("handles a player payload without inventory and blocks unaffordable purchases", () => {
    const withoutInventory = { ...player }
    delete withoutInventory.inventory
    useGameStore.setState({ player: withoutInventory, awareness: awareness([merchant]) })
    render(<TradePanel />)

    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled()
    expect(screen.queryByText("Sell")).not.toBeInTheDocument()
  })

  it("uses zero gold for a missing player but still offers unpriced and free items", () => {
    useGameStore.setState({
      awareness: awareness([{
        ...merchant,
        items: [
          { id: "gift", name: "Gift", description: "A gift" },
          { id: "sample", name: "Sample", description: "A sample", price: null },
          { id: "free", name: "Free vial", description: "An empty vial", price: 0 },
          potion,
        ],
      }]),
    })
    render(<TradePanel />)

    const [unpriced, unknownPrice, free, paid] = screen.getAllByRole("button", { name: "Buy" })
    expect(unpriced).toBeEnabled()
    expect(unknownPrice).toBeEnabled()
    expect(free).toBeEnabled()
    expect(paid).toBeDisabled()
    expect(screen.getByText("0g")).toBeVisible()
    expect(screen.queryByRole("button", { name: "Sell" })).not.toBeInTheDocument()
  })

  it("allows exact balances and blocks purchases or sales one gold above either balance", () => {
    useGameStore.setState({
      player: { ...player, inventory: [gem, { ...gem, id: "diamond", name: "Diamond", price: 11 }] },
      awareness: awareness([{
        ...merchant,
        gold: 10,
        items: [{ ...potion, price: 10 }, { ...potion, id: "elixir", name: "Elixir", price: 11 }],
      }]),
    })
    render(<TradePanel />)

    const [affordableBuy, expensiveBuy] = screen.getAllByRole("button", { name: "Buy" })
    const [affordableSell, expensiveSell] = screen.getAllByRole("button", { name: "Sell" })
    expect(affordableBuy).toBeEnabled()
    expect(affordableSell).toBeEnabled()
    expect(expensiveBuy).toBeDisabled()
    expect(expensiveSell).toBeDisabled()
    fireEvent.click(expensiveBuy)
    fireEvent.click(expensiveSell)
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("disables all trading while an action is pending, even with sufficient funds", () => {
    useGameStore.setState({
      player: { ...player, gold: 100, inventory: [gem] },
      awareness: awareness([merchant]),
      waitingForAction: true,
    })
    render(<TradePanel />)

    for (const name of ["Buy", "Sell"]) {
      const button = screen.getByRole("button", { name })
      expect(button).toBeDisabled()
      fireEvent.click(button)
    }
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("sends a sale once, locks trading, and renders the successful server update", () => {
    useGameStore.setState({ player: { ...player, inventory: [gem] }, awareness: awareness([merchant]) })
    render(<TradePanel />)

    fireEvent.click(screen.getByRole("button", { name: "Sell" }))
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "sell", params: { merchant_id: "alchemist", item_id: "gem" },
    })
    expect(screen.getByRole("button", { name: "Sell" })).toBeDisabled()
    fireEvent.click(screen.getByRole("button", { name: "Sell" }))
    expect(wsClient.send).toHaveBeenCalledTimes(1)

    act(() => useGameStore.getState().onActionResult({
      type: "action_result",
      actor: "hero",
      action: "sell",
      mode: "peaceful",
      player: { ...player, gold: 20, inventory: [] },
      awareness: awareness([{ ...merchant, gold: 90, items: [potion, gem] }]),
      location: { current_location: "Market", current_location_id: "market", description: "A market", region_id: "town", paths: [] },
      events: [],
    }))

    expect(screen.getByText("90g")).toBeVisible()
    expect(screen.getByText("Ruby")).toBeVisible()
    expect(screen.queryByRole("button", { name: "Sell" })).not.toBeInTheDocument()
    for (const button of screen.getAllByRole("button", { name: "Buy" })) {
      expect(button).toBeEnabled()
    }
  })

  it("buys an unpriced item and allows retry after a server error releases the pending action", () => {
    useGameStore.setState({
      player,
      awareness: awareness([{ ...merchant, items: [{ ...potion, price: null }] }]),
    })
    render(<TradePanel />)

    fireEvent.click(screen.getByRole("button", { name: "Buy" }))
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "buy", params: { merchant_id: "alchemist", item_id: "potion" },
    })
    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled()

    // Error presentation belongs to the game screen; this panel only unlocks trading.
    act(() => useGameStore.getState().onError({ type: "error", message: "Merchant is busy" }))
    expect(screen.getByText("Healing potion")).toBeVisible()
    expect(screen.getByRole("button", { name: "Buy" })).toBeEnabled()
    fireEvent.click(screen.getByRole("button", { name: "Buy" }))
    expect(wsClient.send).toHaveBeenCalledTimes(2)
    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled()
  })
})
