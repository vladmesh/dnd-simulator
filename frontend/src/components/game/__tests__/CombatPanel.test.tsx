import { render, screen, act } from "@testing-library/react"
import { describe, it, expect, beforeEach, vi } from "vitest"
import "@/i18n"

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
import { CombatPanel } from "../CombatPanel"
import type { CombatAwareness, PlayerStatus } from "@/types/game"

function makePlayer(overrides?: Partial<PlayerStatus>): PlayerStatus {
  return {
    player_id: "p1",
    name: "Hero",
    race: "human",
    char_class: "paladin",
    level: 1,
    experience: 0,
    level_up_available: false,
    xp_to_next_level: 300,
    alignment: "neutral",
    hp: 12,
    max_hp: 12,
    ac: 15,
    gold: 0,
    location_id: "town",
    ability_scores: { str: 16, dex: 10, con: 14, int: 10, wis: 12, cha: 14 },
    resource_pools: [],
    ...overrides,
  }
}

function makeAwareness(overrides?: Partial<CombatAwareness>): CombatAwareness {
  return {
    self_hp: 12,
    self_max_hp: 12,
    self_ac: 15,
    self_speed: 30,
    self_weapon: "longsword",
    self_weapon_damage: "1d8 slashing",
    self_conditions: [],
    nearby: [],
    round_number: 1,
    available_actions: [],
    available_items: [],
    self_resource_pools: [],
    ...overrides,
  }
}

beforeEach(() => {
  useGameStore.setState({
    mode: "combat",
    awareness: null,
    player: null,
  })
})

describe("CombatPanel — player is canonical HP/AC source", () => {
  it("renders HP, max HP, AC from player slice, not from awareness.self_*", () => {
    useGameStore.setState({
      player: makePlayer({ hp: 20, max_hp: 20, ac: 18 }),
      // stale awareness snapshot — should be ignored for HP/AC
      awareness: makeAwareness({ self_hp: 12, self_max_hp: 12, self_ac: 15 }),
    })

    render(<CombatPanel />)

    expect(screen.getByText(/20\s*\/\s*20/)).toBeInTheDocument()
    expect(screen.queryByText(/12\s*\/\s*12/)).not.toBeInTheDocument()
    expect(screen.getByText(/AC[^0-9]*18/)).toBeInTheDocument()
  })

  it("re-renders new HP when player is updated without any awareness change (level-up scenario)", () => {
    useGameStore.setState({
      player: makePlayer({ hp: 12, max_hp: 12 }),
      awareness: makeAwareness({ self_hp: 12, self_max_hp: 12 }),
    })

    render(<CombatPanel />)
    expect(screen.getByText(/12\s*\/\s*12/)).toBeInTheDocument()

    act(() => {
      useGameStore.setState({
        player: makePlayer({ hp: 20, max_hp: 20, level: 2 }),
      })
    })

    expect(screen.getByText(/20\s*\/\s*20/)).toBeInTheDocument()
    expect(screen.queryByText(/12\s*\/\s*12/)).not.toBeInTheDocument()
  })

  it("renders spell slots from player.resource_pools, not awareness.self_resource_pools", () => {
    useGameStore.setState({
      player: makePlayer({
        resource_pools: [{ id: "spell_slot_1", max_uses: 2, current_uses: 2 }],
      }),
      awareness: makeAwareness({
        // stale: awareness has no spell slots, but player does
        self_resource_pools: [],
      }),
    })

    render(<CombatPanel />)

    expect(screen.getByText(/spell slots/i)).toBeInTheDocument()
    expect(screen.getByText(/lv\s*1/i)).toBeInTheDocument()
  })
})
