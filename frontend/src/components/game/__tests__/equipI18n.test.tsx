import { render, screen } from "@testing-library/react"
import { describe, it, expect, beforeAll, afterAll } from "vitest"
import i18n from "@/i18n"
import { getActionLabel } from "../action-bar/utils"

// Mock wsClient BEFORE store imports it
import { vi } from "vitest"
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

const SLOT_ACTIONS = [
  "equip_armor",
  "unequip_armor",
  "equip_shield",
  "unequip_shield",
  "equip_head",
  "unequip_head",
  "equip_feet",
  "unequip_feet",
  "equip_ring",
  "unequip_ring",
]

describe("equip/unequip slot labels — i18n", () => {
  beforeAll(async () => {
    await i18n.changeLanguage("ru")
  })
  afterAll(async () => {
    await i18n.changeLanguage("en")
  })

  it("resolves every slot action to a real translation, not the raw id", () => {
    const t = i18n.getFixedT("ru", "game")
    for (const name of SLOT_ACTIONS) {
      const label = getActionLabel((k) => t(k.replace("game:", "")), name)
      expect(label).not.toBe(name)
      expect(label.length).toBeGreaterThan(0)
    }
  })
})

describe("InventoryPanel — bag buttons use i18n, not hardcoded literals", () => {
  beforeAll(async () => {
    await i18n.changeLanguage("ru")
  })
  afterAll(async () => {
    await i18n.changeLanguage("en")
  })

  it("renders translated Use/Equip labels, not EQUIP/USE literals", () => {
    useGameStore.setState({
      player: {
        id: "p1",
        name: "Hero",
        equipped: [],
        inventory: [
          { id: "pot1", name: "Зелье", type: "potion", description: "heals" },
          { id: "sw1", name: "Меч", type: "weapon", description: "a sword" },
        ],
      },
    } as never)

    render(<InventoryPanel />)

    expect(screen.queryByText("USE")).toBeNull()
    expect(screen.queryByText("EQUIP")).toBeNull()
    expect(screen.getByText(i18n.getFixedT("ru", "game")("use"))).toBeTruthy()
    expect(screen.getByText(i18n.getFixedT("ru", "game")("equip"))).toBeTruthy()
  })
})
