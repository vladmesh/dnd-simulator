import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, it, expect, beforeEach, vi } from "vitest"
import i18n from "@/i18n"

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
import { Perception } from "../Perception"
import type { CombatAwareness, NearbyEntity, PeacefulAwareness } from "@/types/game"

const sendMock = wsClient.send as unknown as ReturnType<typeof vi.fn>

function makeAwareness(nearby: NearbyEntity[]): PeacefulAwareness {
  return {
    hour: 12,
    day: 1,
    month: 1,
    year: 1,
    weather: {},
    location_name: "Town",
    region_name: "Region",
    nearby,
  }
}

beforeEach(() => {
  sendMock.mockReset()
  useGameStore.setState({
    mode: "peaceful",
    awareness: null,
    isMyTurn: true,
  })
})

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage("en")
  })
})

function makeCombatAwareness(nearby: NearbyEntity[]): CombatAwareness {
  return {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "Longsword",
    self_weapon_damage: "1d8",
    self_conditions: [],
    nearby: nearby as unknown as CombatAwareness["nearby"],
    round_number: 1,
    available_actions: [],
    available_items: [],
    self_resource_pools: [
      { id: "spell_slot_1", max_uses: 2, current_uses: 2 },
    ],
  }
}

describe("Perception — corpse/lootable entities hide Attack/Talk", () => {
  it("hides Attack and Talk for a lootable (corpse/container) entity", () => {
    useGameStore.setState({
      awareness: makeAwareness([
        { id: "goblin-1", description: "Dead Goblin", lootable: true },
      ]),
    })

    render(<Perception />)

    expect(screen.queryByText("Attack")).not.toBeInTheDocument()
    expect(screen.queryByText("Talk")).not.toBeInTheDocument()
  })

  it("shows Attack and Talk for a living (non-lootable) entity", () => {
    useGameStore.setState({
      awareness: makeAwareness([
        { id: "goblin-2", description: "Goblin", lootable: false },
      ]),
    })

    render(<Perception />)

    expect(screen.getByText("Attack")).toBeInTheDocument()
    expect(screen.getByText("Talk")).toBeInTheDocument()
  })
})

describe("Perception — target-aware attack accessibility", () => {
  // Two same-race NPCs: their perceived descriptions collide ("человек"/"Goblin"), so the
  // accessible name must key on the unique entity id — matching the action-bar contract.
  const twoTargets: NearbyEntity[] = [
    { id: "goblin_1", description: "Goblin", lootable: false },
    { id: "goblin_2", description: "Goblin", lootable: false },
  ]

  it("gives each nearby Attack control a unique target-aware accessible name and sends its id", async () => {
    useGameStore.setState({ awareness: makeAwareness(twoTargets) })
    render(<Perception />)

    const attackOne = screen.getByRole("button", { name: "Attack goblin_1" })
    const attackTwo = screen.getByRole("button", { name: "Attack goblin_2" })
    expect(attackOne).not.toBe(attackTwo)

    await userEvent.click(attackTwo)
    expect(sendMock).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_2" },
    })
  })

  it("keeps the open inspect modal's Attack control target-aware and unambiguous", async () => {
    useGameStore.setState({ awareness: makeAwareness(twoTargets) })
    render(<Perception />)

    await userEvent.click(screen.getByRole("button", { name: "Inspect goblin_1" }))

    // Radix hides the background list from the a11y tree, so the modal's control is
    // the only "Attack goblin_1" button reachable by role + name.
    const modalAttack = screen.getByRole("button", { name: "Attack goblin_1" })
    expect(modalAttack).toBeInTheDocument()
    await userEvent.click(modalAttack)
    expect(sendMock).toHaveBeenCalledWith({
      type: "action",
      name: "attack",
      params: { target_id: "goblin_1" },
    })
  })

  it("localizes the nearby Attack accessible name in Russian", async () => {
    await act(async () => {
      await i18n.changeLanguage("ru")
    })
    useGameStore.setState({ awareness: makeAwareness(twoTargets) })
    render(<Perception />)

    expect(screen.getByRole("button", { name: "Атаковать goblin_1" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Атаковать goblin_2" })).toBeInTheDocument()
  })

  it.each([
    ["en", "Attack goblin_1", "Attack goblin_1 + Smite (slot 1)"],
    ["ru", "Атаковать goblin_1", "Атаковать goblin_1 + Кара (ячейка 1)"],
  ])("exposes smite menu items selectable by localized accessible name (%s)", async (lang, normal, withSmite) => {
    await act(async () => {
      await i18n.changeLanguage(lang)
    })
    useGameStore.setState({
      mode: "combat",
      awareness: makeCombatAwareness([{ id: "goblin_1", description: "Goblin", is_hostile: true }]),
    })
    render(<Perception />)

    await userEvent.click(screen.getByRole("button", { name: normal }))

    const items = screen.getAllByRole("menuitem").map((el) => (el.textContent ?? "").trim())
    // The plain-attack item is exactly the target label; the smite item prefixes it.
    expect(items).toContain(normal)
    expect(items.some((label) => label.startsWith(withSmite))).toBe(true)
  })
})
