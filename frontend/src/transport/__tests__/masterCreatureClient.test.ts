import { afterEach, describe, expect, it, vi } from "vitest"
import { api } from "@/transport/apiClient"
import type { PatchCreatureRequest, SpawnCreatureRequest } from "@/types/api"

function mockFetch(response: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function sentRequest(fetchMock: ReturnType<typeof mockFetch>) {
  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  return { path, init, body: JSON.parse(init.body as string) as unknown }
}

afterEach(() => vi.unstubAllGlobals())

describe("GM creature requests on the wire", () => {
  it("POSTs every supported spawn field as JSON to the session creatures endpoint", async () => {
    const fetchMock = mockFetch({ id: "wolf_1", name: "Wolf" })
    const payload: SpawnCreatureRequest = {
      id: "wolf_1",
      name: "Wolf",
      entity_type: "monster",
      start_location: "forest",
      hp: 11,
      ac: 13,
      speed: 40,
      attacks: [{ name: "Bite", to_hit: 4, damage: "2d4+2" }],
      ability_scores: { STR: 12, DEX: 15 },
      combat_position: [10, 5],
      role: null,
      personality: null,
      settlement_id: null,
      ai: "llm",
      xp_value: 50,
    }

    await api.master.spawnCreature("s-1", payload)

    const { path, init, body } = sentRequest(fetchMock)
    expect(path).toBe("/api/master/sessions/s-1/creatures")
    expect(init.method).toBe("POST")
    expect(init.headers).toEqual({ "Content-Type": "application/json" })
    expect(body).toEqual(payload)
  })

  it("PATCHes every supported creature field as JSON to the creature endpoint", async () => {
    const fetchMock = mockFetch({ message: "ok" })
    const payload: PatchCreatureRequest = {
      current_hp: 5,
      max_hp: 20,
      ac: 15,
      location_id: "town",
      conditions: ["prone"],
      gold: 7,
      level: 3,
      experience: 900,
      xp_value: 0,
      resource_pools: [{ id: "second_wind", max_uses: 1, current_uses: 0, reset_on: "short_rest" }],
      personality: null,
    }

    await api.master.patchCreature("s-1", "npc_1", payload)

    const { path, init, body } = sentRequest(fetchMock)
    expect(path).toBe("/api/master/sessions/s-1/creatures/npc_1")
    expect(init.method).toBe("PATCH")
    expect(init.headers).toEqual({ "Content-Type": "application/json" })
    expect(body).toEqual(payload)
  })
})
