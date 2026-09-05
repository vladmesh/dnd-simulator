import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from "vitest"
import i18n from "@/i18n"
import type { ItemInfo } from "@/types/game"

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

import { wsClient } from "@/transport/wsClient"
import { useGameStore } from "@/store/gameStore"
import { InventoryPanel } from "../InventoryPanel"
import { TradePanel } from "../TradePanel"
import { LootView } from "../LootPanel"

const ru = i18n.getFixedT("ru", "game")
const en = i18n.getFixedT("en", "game")

const PLATE_ARMOR = {
  id: "plate1",
  name: "Латы",
  type: "armor",
  description: "Plate Armor",
  price: 1500,
  props: { kind: "armor", category: "heavy", base_ac: 18, max_dex_bonus: 0 },
}

const FLAME_SWORD: ItemInfo = {
  id: "sword1",
  name: "Огненный меч",
  type: "weapon",
  description: "Flame Sword (weapon: 1d8 slashing, 1d6 fire, reach 5ft [magic, +1])",
  price: 500,
  props: {
    kind: "weapon",
    damage: [
      { dice: "1d8", type: "slashing" },
      { dice: "1d6", type: "fire" },
    ],
    reach: 5,
    category: "martial",
    ability: "str",
    modifier: 1,
    is_magic: true,
    is_finesse: false,
    is_two_handed: false,
    is_light: false,
    is_heavy: false,
    conditions: [],
  },
}

const HEALING_POTION = {
  id: "pot1",
  name: "Зелье лечения",
  type: "potion",
  description: "Healing Potion (heals 2d4+2 HP)",
  props: { kind: "potion", heal_dice: "2d4+2" },
}

const RING_OF_PROTECTION = {
  slot: "ring",
  item_id: "ring1",
  name: "Кольцо защиты",
  description: "Ring of Protection (+1 AC)",
  props: {
    kind: "accessory",
    slot: "ring",
    modifiers: [{ stat: "ac", op: "add", value: 1 }],
  },
}

function setPlayer(overrides: Record<string, unknown>) {
  useGameStore.setState({
    waitingForAction: false,
    player: {
      player_id: "p1",
      name: "Hero",
      gold: 10000,
      equipped: [],
      inventory: [],
      ...overrides,
    },
  } as never)
}

function setMerchant(items: unknown[]) {
  useGameStore.setState({
    awareness: {
      hour: 12,
      day: 1,
      month: 1,
      year: 1,
      weather: {},
      location_name: "Town",
      region_name: "Region",
      nearby: [],
      merchants: [{ id: "m1", name: "Торговец", gold: 5000, items }],
    },
  } as never)
}

describe("ItemDetails card — RU", () => {
  beforeAll(async () => {
    await i18n.changeLanguage("ru")
  })
  afterAll(async () => {
    await i18n.changeLanguage("en")
  })
  beforeEach(() => {
    vi.mocked(wsClient.send).mockClear()
  })

  it("bag armor renders base AC, dex cap and category with russian labels", () => {
    setPlayer({ inventory: [PLATE_ARMOR] })
    const { container } = render(<InventoryPanel />)
    expect(container.textContent).toContain(ru("item_base_ac", { n: 18 }))
    expect(container.textContent).toContain(ru("item_max_dex", { n: 0 }))
    expect(container.textContent).toContain(ru("armor_cat_heavy"))
  })

  it("merchant flame sword renders both damage components, +1 and magic flag", () => {
    setPlayer({ inventory: [] })
    setMerchant([FLAME_SWORD])
    const { container } = render(<TradePanel />)
    expect(container.textContent).toContain(`1d8 ${ru("dmg_slashing")}`)
    expect(container.textContent).toContain(`1d6 ${ru("dmg_fire")}`)
    expect(container.textContent).toContain("+1")
    expect(container.textContent).toContain(ru("prop_magic"))
    expect(container.textContent).toContain(ru("wpn_cat_martial"))
  })

  it("loot flame sword renders structured item properties", () => {
    const { container } = render(
      <LootView
        holder={{
          id: "corpse1",
          name: "Павший маг",
          description: "Тело мага",
          lootable: true,
          loot_items: [FLAME_SWORD],
        }}
      />,
    )

    expect(container.textContent).toContain(`1d8 ${ru("dmg_slashing")}`)
    expect(container.textContent).toContain(`1d6 ${ru("dmg_fire")}`)
    expect(container.textContent).toContain(ru("prop_magic"))
  })

  it("equipped ring of protection renders +1 AC", () => {
    setPlayer({ equipped: [RING_OF_PROTECTION] })
    const { container } = render(<InventoryPanel />)
    expect(container.textContent).toContain(`+1 ${ru("stat_ac")}`)
  })

  it("healing potion renders heal dice", () => {
    setPlayer({ inventory: [HEALING_POTION] })
    const { container } = render(<InventoryPanel />)
    expect(container.textContent).toContain(ru("item_heals", { dice: "2d4+2" }))
  })

  it("item without props falls back to description", () => {
    setPlayer({
      inventory: [{ id: "rock1", name: "Камень", type: "misc", description: "Просто камень" }],
    })
    const { container } = render(<InventoryPanel />)
    expect(container.textContent).toContain("Просто камень")
  })
})

describe("ItemDetails card — EN", () => {
  beforeEach(() => {
    vi.mocked(wsClient.send).mockClear()
  })

  it("bag armor renders english labels", () => {
    setPlayer({ inventory: [PLATE_ARMOR] })
    const { container } = render(<InventoryPanel />)
    expect(container.textContent).toContain(en("item_base_ac", { n: 18 }))
    expect(container.textContent).toContain(en("armor_cat_heavy"))
  })
})

describe("ItemDetails — click behavior unchanged", () => {
  beforeEach(() => {
    vi.mocked(wsClient.send).mockClear()
  })

  it("clicking equipped slot still sends unequip action", () => {
    setPlayer({
      equipped: [
        {
          slot: "armor",
          item_id: "plate1",
          name: "Латы",
          description: "Plate Armor",
          props: PLATE_ARMOR.props,
        },
      ],
    })
    render(<InventoryPanel />)
    fireEvent.click(screen.getByText("Латы"))
    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "unequip_armor",
      params: undefined,
    })
  })

  it("clicking buy still sends buy action with merchant and item ids", () => {
    setPlayer({ inventory: [] })
    setMerchant([FLAME_SWORD])
    render(<TradePanel />)
    const buyButtons = screen.getAllByRole("button", { name: en("buy") })
    fireEvent.click(buyButtons[buyButtons.length - 1])
    expect(wsClient.send).toHaveBeenCalledWith({
      type: "action",
      name: "buy",
      params: { merchant_id: "m1", item_id: "sword1" },
    })
  })
})
