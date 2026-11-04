import { afterEach, describe, expect, it, vi } from "vitest"
import { masterCreatureClient as client } from "@/transport/masterCreatureClient"
import type {
  GiveItemRequest,
  PatchNationRequest,
  PatchSettlementRequest,
  SetActivationOverrideRequest,
  SetActivationTriggerRequest,
  SetBrainRequest,
} from "@/types/api"

function mockFetch(response: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function sent(fetchMock: ReturnType<typeof mockFetch>) {
  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  return { path, method: init.method, body: init.body === undefined ? undefined : (JSON.parse(init.body as string) as unknown) }
}

afterEach(() => vi.unstubAllGlobals())

const brain = { brain: "rule" } as unknown as SetBrainRequest
const activation = { override: "active" } as unknown as SetActivationOverrideRequest
const trigger = { on: { type: "combat_started" }, until: { type: "combat_ended" } } as unknown as SetActivationTriggerRequest
const give = { ref: "longsword" } as unknown as GiveItemRequest
const nation = { treasury: 100 } as unknown as PatchNationRequest
const settlement = { prosperity: 3 } as unknown as PatchSettlementRequest

type Case = [string, () => Promise<unknown>, string, string, unknown]

const cases: Case[] = [
  ["all creatures", () => client.getCreatures("s1"), "GET", "/api/master/sessions/s1/creatures", undefined],
  ["creatures with empty filters", () => client.getCreatures("s1", {}), "GET", "/api/master/sessions/s1/creatures", undefined],
  [
    "creatures with every filter",
    () => client.getCreatures("s1", { entity_type: "npc", location_id: "old mill", active: true }),
    "GET",
    "/api/master/sessions/s1/creatures?entity_type=npc&location_id=old+mill&active=true",
    undefined,
  ],
  ["creature", () => client.getCreature("s1", "wolf_1"), "GET", "/api/master/sessions/s1/creatures/wolf_1", undefined],
  ["delete creature", () => client.deleteCreature("s1", "wolf_1"), "DELETE", "/api/master/sessions/s1/creatures/wolf_1", undefined],
  ["set brain", () => client.setBrain("s1", "wolf_1", brain), "PUT", "/api/master/sessions/s1/creatures/wolf_1/brain", brain],
  ["set activation", () => client.setCreatureActivation("s1", "wolf_1", activation), "PUT", "/api/master/sessions/s1/creatures/wolf_1/activation", activation],
  [
    "set activation trigger",
    () => client.setActivationTrigger("s1", "wolf_1", "night/watch", trigger),
    "PUT",
    "/api/master/sessions/s1/creatures/wolf_1/triggers/night%2Fwatch",
    trigger,
  ],
  ["give item", () => client.giveItem("s1", "wolf_1", give), "POST", "/api/master/sessions/s1/creatures/wolf_1/items", give],
  ["patch nation", () => client.patchNation("s1", "kingdom", nation), "PATCH", "/api/master/sessions/s1/nations/kingdom", nation],
  ["patch settlement", () => client.patchSettlement("s1", "town", settlement), "PATCH", "/api/master/sessions/s1/settlements/town", settlement],
]

describe("masterCreatureClient GM routes on the wire", () => {
  it.each(cases)("%s", async (_name, call, method, path, body) => {
    const fetchMock = mockFetch({ marker: path })
    await expect(call()).resolves.toEqual({ marker: path })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(sent(fetchMock)).toEqual({ path, method, body })
  })
})
