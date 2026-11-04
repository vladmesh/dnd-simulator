import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "@/transport/requestCore"
import { masterWorldClient as client } from "@/transport/masterWorldClient"
import type { AssembleWorldRequest, CreateWorldRequest, EntityEntry, ForkWorldRequest, UpdateLayerFileRequest } from "@/types/api"

function mockFetch(response: unknown = { ok: true }) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function sent(fetchMock: ReturnType<typeof mockFetch>) {
  const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  return { path, method: init.method, body: init.body === undefined ? undefined : (JSON.parse(init.body as string) as unknown) }
}

afterEach(() => vi.unstubAllGlobals())

const assemble = { world_id: "w", layers: {} } as unknown as AssembleWorldRequest
const world = { id: "w", name: "World" } as unknown as CreateWorldRequest
const fork = { new_id: "w2" } as unknown as ForkWorldRequest
const layerFile = { content: "regions: []" } as unknown as UpdateLayerFileRequest
const entity = { id: "npc_1", name: "Bob" } as unknown as EntityEntry

type Case = [string, () => Promise<unknown>, string, string, unknown]

const cases: Case[] = [
  ["library templates", () => client.getLibraryTemplates("politics"), "GET", "/api/master/library/politics", undefined],
  ["library templates by geography", () => client.getLibraryTemplates("politics", "north coast"), "GET", "/api/master/library/politics?geography=north%20coast", undefined],
  ["assemble world", () => client.assembleWorld(assemble), "POST", "/api/master/worlds/assemble", assemble],
  ["world list", () => client.getWorlds(), "GET", "/api/master/worlds", undefined],
  ["world list by language", () => client.getWorlds("ru"), "GET", "/api/master/worlds?lang=ru", undefined],
  ["world", () => client.getWorld("w"), "GET", "/api/master/worlds/w", undefined],
  ["manifest", () => client.getWorldManifest("w"), "GET", "/api/master/worlds/w/manifest", undefined],
  ["manifest by language", () => client.getWorldManifest("w", "en gb"), "GET", "/api/master/worlds/w/manifest?lang=en%20gb", undefined],
  ["fork layer", () => client.forkLayer("w", "ecology"), "POST", "/api/master/worlds/w/fork/ecology", undefined],
  ["layer files", () => client.getLayerFiles("w", "ecology"), "GET", "/api/master/worlds/w/layers/ecology/files", undefined],
  ["layer file", () => client.getLayerFile("w", "ecology", "sub dir/monsters.yaml"), "GET", "/api/master/worlds/w/layers/ecology/files/sub%20dir%2Fmonsters.yaml", undefined],
  ["update layer file", () => client.updateLayerFile("w", "ecology", "monsters.yaml", layerFile), "PUT", "/api/master/worlds/w/layers/ecology/files/monsters.yaml", layerFile],
  ["create world", () => client.createWorld(world), "POST", "/api/master/worlds", world],
  ["update world", () => client.updateWorld("w", world), "PUT", "/api/master/worlds/w", world],
  ["fork world", () => client.forkWorld("w", fork), "POST", "/api/master/worlds/w/fork", fork],
  ["delete world", () => client.deleteWorld("w"), "DELETE", "/api/master/worlds/w", undefined],
  ["refs", () => client.getRefs("w", "items"), "GET", "/api/master/worlds/w/refs/items", undefined],
  ["entity list", () => client.listEntities("w", "npcs"), "GET", "/api/master/worlds/w/entities/npcs", undefined],
  ["entity", () => client.getEntity("w", "npcs", "npc_1"), "GET", "/api/master/worlds/w/entities/npcs/npc_1", undefined],
  ["create entity", () => client.createEntity("w", "npcs", "npc_1", entity), "POST", "/api/master/worlds/w/entities/npcs/npc_1", entity],
  ["update entity", () => client.updateEntity("w", "npcs", "npc_1", entity), "PUT", "/api/master/worlds/w/entities/npcs/npc_1", entity],
  ["delete entity", () => client.deleteEntity("w", "npcs", "npc_1"), "DELETE", "/api/master/worlds/w/entities/npcs/npc_1", undefined],
]

describe("masterWorldClient on the wire", () => {
  it.each(cases)("%s", async (_name, call, method, path, body) => {
    const fetchMock = mockFetch({ marker: path })
    await expect(call()).resolves.toEqual({ marker: path })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(sent(fetchMock)).toEqual({ path, method, body })
  })

  it("rejects with ApiError carrying the parsed error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, text: async () => JSON.stringify({ detail: "World not found" }) }),
    )
    const error = await client.getWorld("missing").catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
    expect((error as ApiError).detailMessage()).toBe("World not found")
  })
})
