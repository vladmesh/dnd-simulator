import { describe, it, expect, beforeEach, vi } from "vitest"

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
import { extractGameTime } from "@/store/slices/turnSlice"
import type { Awareness, PlayerStatus, TurnBudget } from "@/types/game"
import type { TurnMessage, RoundResultMessage } from "@/types/ws"

const budget: TurnBudget = { actions: 1, bonus_actions: 1, movement_remaining: 30, reaction: 1 }

const player: PlayerStatus = {
  player_id: "p1",
  name: "Hero",
  race: "human",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "N",
  hp: 10,
  max_hp: 10,
  ac: 15,
  gold: 0,
  location_id: "loc1",
  ability_scores: { str: 15, dex: 12, con: 14, int: 10, wis: 10, cha: 8 },
}

const peaceful = {
  hour: 9,
  day: 2,
  month: 3,
  year: 1,
  nearby: [],
  turn_budget: budget,
} as unknown as Awareness

const combat = { self_hp: 10, nearby: [], round_number: 1 } as unknown as Awareness

beforeEach(() => {
  useGameStore.setState({ gameTime: null, budget: null, log: [], player: null })
})

describe("extractGameTime", () => {
  it("returns time fields from peaceful awareness", () => {
    expect(extractGameTime(peaceful)).toEqual({ hour: 9, day: 2, month: 3, year: 1 })
  })
  it("returns null for combat awareness (no hour)", () => {
    expect(extractGameTime(combat)).toBeNull()
  })
})

describe("turn handlers", () => {
  it("onTurn extracts game time and falls back to awareness turn_budget", () => {
    const msg: TurnMessage = {
      type: "turn",
      mode: "peaceful",
      awareness: peaceful,
      events: [],
      player,
      location: { current_location: "L", current_location_id: "loc1", description: "", region_id: "r", paths: [] },
    }
    useGameStore.getState().onTurn(msg)
    const s = useGameStore.getState()
    expect(s.gameTime).toEqual({ hour: 9, day: 2, month: 3, year: 1 })
    expect(s.budget).toEqual(budget)
    expect(s.isMyTurn).toBe(true)
  })

  it("onRoundResult in combat leaves gameTime untouched", () => {
    useGameStore.setState({ gameTime: { hour: 5, day: 1, month: 1, year: 1 } })
    const msg: RoundResultMessage = {
      type: "round_result",
      mode: "combat",
      awareness: combat,
      events: [],
      player,
      location: { current_location: "L", current_location_id: "loc1", description: "", region_id: "r", paths: [] },
    }
    useGameStore.getState().onRoundResult(msg)
    const s = useGameStore.getState()
    expect(s.gameTime).toEqual({ hour: 5, day: 1, month: 1, year: 1 })
    expect(s.isMyTurn).toBe(false)
  })
})

describe("connect resets turn state", () => {
  it("clears turn fields to defaults on connect", () => {
    useGameStore.setState({
      gameTime: { hour: 5, day: 1, month: 1, year: 1 },
      isMyTurn: true,
      lastError: "old",
      gameOver: true,
    })
    useGameStore.getState().connect("session-2")
    const s = useGameStore.getState()
    expect(s.sessionId).toBe("session-2")
    expect(s.gameTime).toBeNull()
    expect(s.isMyTurn).toBe(false)
    expect(s.lastError).toBeNull()
    expect(s.gameOver).toBe(false)
    expect(s.mode).toBe("peaceful")
  })
})
