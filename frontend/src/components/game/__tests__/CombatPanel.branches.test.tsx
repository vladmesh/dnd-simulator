import { act, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"

// This panel only reads store state; it has no REST calls or user actions.
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
import type { CombatAwareness, PeacefulAwareness, PlayerStatus } from "@/types/game"
import { CombatPanel } from "../CombatPanel"

function makePlayer(overrides: Partial<PlayerStatus> = {}): PlayerStatus {
  return {
    player_id: "p1",
    name: "Hero",
    race: "human",
    char_class: "wizard",
    level: 3,
    experience: 900,
    level_up_available: false,
    xp_to_next_level: 1800,
    alignment: "neutral",
    hp: 20,
    max_hp: 20,
    ac: 12,
    gold: 0,
    location_id: "town",
    ability_scores: { str: 8, dex: 14, con: 14, int: 16, wis: 12, cha: 10 },
    resource_pools: [],
    ...overrides,
  }
}

function makeAwareness(overrides: Partial<CombatAwareness> = {}): CombatAwareness {
  return {
    self_hp: 20,
    self_max_hp: 20,
    self_ac: 12,
    self_speed: 30,
    self_weapon: "quarterstaff",
    self_weapon_damage: "1d6 bludgeoning",
    nearby: [],
    round_number: 3,
    ...overrides,
  }
}

beforeEach(() => {
  useGameStore.setState({ mode: "combat", awareness: null, player: null })
})

describe("CombatPanel — uncovered rendering branches", () => {
  it("stays hidden while awareness is loading, then displays the round and speed", () => {
    useGameStore.setState({ player: makePlayer() })
    render(<CombatPanel />)

    expect(screen.queryByRole("heading", { name: "Combat" })).not.toBeInTheDocument()
    expect(screen.queryByText("Your Stats")).not.toBeInTheDocument()

    act(() => {
      useGameStore.setState({ awareness: makeAwareness({ round_number: 9, self_speed: 0 }) })
    })

    expect(screen.getByRole("heading", { name: "Combat" })).toBeInTheDocument()
    expect(screen.getByText("Round 9")).toBeInTheDocument()
    expect(screen.getByText("Speed: 0ft")).toBeInTheDocument()
  })

  it("waits for the player even when combat awareness has arrived", () => {
    useGameStore.setState({ awareness: makeAwareness() })
    render(<CombatPanel />)

    expect(screen.queryByRole("heading", { name: "Combat" })).not.toBeInTheDocument()
    expect(screen.queryByText("Your Stats")).not.toBeInTheDocument()

    act(() => {
      useGameStore.setState({ player: makePlayer() })
    })

    expect(screen.getByRole("heading", { name: "Combat" })).toBeInTheDocument()
    expect(screen.getByText("Your Stats")).toBeInTheDocument()
  })

  it("does not render combat information for peaceful awareness", () => {
    const awareness: PeacefulAwareness = {
      hour: 12,
      day: 1,
      month: 1,
      year: 1500,
      weather: {},
      location_name: "Town",
      region_name: "Valley",
      nearby: [],
    }
    useGameStore.setState({ player: makePlayer(), awareness })
    render(<CombatPanel />)

    expect(screen.queryByRole("heading", { name: "Combat" })).not.toBeInTheDocument()
    expect(screen.queryByText("Your Stats")).not.toBeInTheDocument()
    expect(screen.queryByText("Spell Slots")).not.toBeInTheDocument()
  })

  it("displays all current conditions and removes them when the list becomes empty", () => {
    useGameStore.setState({
      player: makePlayer(),
      awareness: makeAwareness({ self_conditions: ["poisoned", "prone"] }),
    })
    render(<CombatPanel />)

    expect(screen.getByText("poisoned")).toBeInTheDocument()
    expect(screen.getByText("prone")).toBeInTheDocument()

    act(() => {
      useGameStore.setState({ awareness: makeAwareness({ self_conditions: [] }) })
    })

    expect(screen.queryByText("poisoned")).not.toBeInTheDocument()
    expect(screen.queryByText("prone")).not.toBeInTheDocument()
    expect(screen.getByText("Your Stats")).toBeInTheDocument()
  })

  it("renders safely when optional conditions and resource pools are omitted", () => {
    const player = makePlayer()
    delete player.resource_pools
    useGameStore.setState({ player, awareness: makeAwareness() })
    render(<CombatPanel />)

    expect(screen.getByRole("heading", { name: "Combat" })).toBeInTheDocument()
    expect(screen.getByText("Your Stats")).toBeInTheDocument()
    expect(screen.queryByText("Spell Slots")).not.toBeInTheDocument()
    expect(screen.queryByText(/^Lv\d+$/)).not.toBeInTheDocument()
  })

  it("omits the spell-slot section when all resource pools are non-spell resources", () => {
    useGameStore.setState({
      player: makePlayer({
        resource_pools: [
          { id: "second_wind", max_uses: 1, current_uses: 1 },
          { id: "lay_on_hands", max_uses: 15, current_uses: 0 },
          { id: "other_spell_slot_4", max_uses: 1, current_uses: 1 },
        ],
      }),
      awareness: makeAwareness(),
    })
    render(<CombatPanel />)

    expect(screen.getByText("Your Stats")).toBeInTheDocument()
    expect(screen.queryByText("Spell Slots")).not.toBeInTheDocument()
    expect(screen.queryByText(/^Lv\d+$/)).not.toBeInTheDocument()
  })

  // Exercise health thresholds through visible HP text, not presentation classes.
  it.each([
    { state: "half health", hp: 10, max_hp: 20 },
    { state: "quarter health", hp: 5, max_hp: 20 },
    { state: "zero health", hp: 0, max_hp: 20 },
    { state: "zero maximum health", hp: 0, max_hp: 0 },
  ])("renders $state without losing the stats panel", ({ hp, max_hp }) => {
    useGameStore.setState({ player: makePlayer({ hp, max_hp }), awareness: makeAwareness() })
    render(<CombatPanel />)

    expect(screen.getByText(`HP: ${hp}/${max_hp}`)).toBeInTheDocument()
    expect(screen.getByText("Your Stats")).toBeInTheDocument()
  })

  it("keeps partially spent, depleted and zero-capacity spell levels visible while filtering other pools", () => {
    useGameStore.setState({
      player: makePlayer({
        resource_pools: [
          { id: "spell_slot_1", max_uses: 3, current_uses: 1 },
          { id: "spell_slot_2", max_uses: 2, current_uses: 0 },
          { id: "spell_slot_3", max_uses: 0, current_uses: 0 },
          { id: "other_spell_slot_4", max_uses: 1, current_uses: 1 },
        ],
      }),
      awareness: makeAwareness(),
    })
    render(<CombatPanel />)

    expect(screen.getByText("Spell Slots")).toBeInTheDocument()
    expect(screen.getByText("Lv1")).toBeInTheDocument()
    expect(screen.getByText("Lv2")).toBeInTheDocument()
    expect(screen.getByText("Lv3")).toBeInTheDocument()
    expect(screen.queryByText("Lv4")).not.toBeInTheDocument()
  })
})
