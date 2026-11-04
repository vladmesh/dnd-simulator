import { beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/transport/apiClient"
import { get, post } from "@/transport/requestCore"
import type { CreatePlayerRequest } from "@/types/api"
import type { LevelUpRequest, PlayerStatus } from "@/types/game"

// Keep the player client real; replace the facade and its network boundary.
vi.mock("@/transport/apiClient", async () => {
  const { playerClient } = await import("@/transport/playerClient")
  return { api: { player: playerClient } }
})

vi.mock("@/transport/requestCore", () => ({
  get: vi.fn(),
  post: vi.fn(),
}))

const status: PlayerStatus = {
  player_id: "player-1",
  name: "Mira",
  race: "human",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "neutral",
  hp: 12,
  max_hp: 12,
  ac: 16,
  gold: 0,
  location_id: "village",
  ability_scores: { str: 15, dex: 12, con: 14, int: 8, wis: 13, cha: 10 },
  journey: null,
  equipped: [],
  inventory: [],
  resource_pools: [],
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe("playerClient", () => {
  it("gets setup configuration and preserves a zero starting-gold value", async () => {
    const config = { starting_gold: 0, point_buy_budget: 27 }
    vi.mocked(get).mockResolvedValue(config)

    await expect(api.player.getSetupConfig()).resolves.toEqual(config)

    expect(get).toHaveBeenCalledExactlyOnceWith("/api/player/setup-config")
    expect(post).not.toHaveBeenCalled()
  })

  it("propagates setup configuration failures", async () => {
    const error = new Error("Setup configuration unavailable")
    vi.mocked(get).mockRejectedValue(error)

    await expect(api.player.getSetupConfig()).rejects.toBe(error)

    expect(get).toHaveBeenCalledExactlyOnceWith("/api/player/setup-config")
  })

  it("posts all character creation options to the specified session and returns its status", async () => {
    const character: CreatePlayerRequest = {
      name: status.name,
      race: status.race,
      char_class: status.char_class,
      alignment: status.alignment,
      appearance: "A weathered traveler",
      start_location: "village",
      ability_scores: { ...status.ability_scores },
      fighting_style: "defense",
      combat_position: [0, 5],
    }
    vi.mocked(post).mockResolvedValue(status)

    await expect(api.player.createCharacter("session-creation", character)).resolves.toEqual(status)

    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/api/player/sessions/session-creation/character",
      character,
    )
    expect(get).not.toHaveBeenCalled()
  })

  it("allows character creation with only the required ability scores", async () => {
    const character: CreatePlayerRequest = { ability_scores: { ...status.ability_scores } }
    vi.mocked(post).mockResolvedValue(status)

    await expect(api.player.createCharacter("session-minimal", character)).resolves.toEqual(status)

    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/api/player/sessions/session-minimal/character",
      { ability_scores: status.ability_scores },
    )
  })

  it("propagates character creation failures without retrying", async () => {
    const character: CreatePlayerRequest = { ability_scores: { ...status.ability_scores } }
    const error = new Error("Invalid ability scores")
    vi.mocked(post).mockRejectedValue(error)

    await expect(api.player.createCharacter("session-invalid", character)).rejects.toBe(error)

    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/api/player/sessions/session-invalid/character",
      character,
    )
  })

  // apiClient.test.ts already covers the getStatus error path.
  it("gets the specified session's status, preserving empty inventories and null journeys", async () => {
    vi.mocked(get).mockResolvedValue(status)

    await expect(api.player.getStatus("session-status")).resolves.toEqual(status)

    expect(get).toHaveBeenCalledExactlyOnceWith("/api/player/sessions/session-status/status")
    expect(post).not.toHaveBeenCalled()
  })

  it("posts a fighting-style choice on level-up and returns the updated player", async () => {
    const body: LevelUpRequest = { fighting_style: "archery" }
    const updatedStatus: PlayerStatus = { ...status, level: 2, hp: 20, max_hp: 20 }
    vi.mocked(post).mockResolvedValue(updatedStatus)

    await expect(api.player.levelUp("session-level-up", body)).resolves.toEqual(updatedStatus)

    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/api/player/sessions/session-level-up/level-up",
      body,
    )
    expect(get).not.toHaveBeenCalled()
  })

  it("sends an empty level-up body when no optional choice is needed", async () => {
    const updatedStatus: PlayerStatus = { ...status, level: 3 }
    vi.mocked(post).mockResolvedValue(updatedStatus)

    await expect(api.player.levelUp("session-no-choice", {})).resolves.toEqual(updatedStatus)

    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/api/player/sessions/session-no-choice/level-up",
      {},
    )
  })

  it("propagates a rejected level-up without retrying", async () => {
    const error = new Error("Not enough experience")
    vi.mocked(post).mockRejectedValue(error)

    await expect(api.player.levelUp("session-not-ready", {})).rejects.toBe(error)

    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/api/player/sessions/session-not-ready/level-up",
      {},
    )
  })
})
