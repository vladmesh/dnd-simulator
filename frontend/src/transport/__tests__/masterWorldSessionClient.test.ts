import { afterEach, describe, expect, it, vi } from "vitest"
import { api } from "@/transport/apiClient"
import type { EntityEntry } from "@/types/api"

function mockFetch(response: unknown = { message: "ok" }) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

type Call = { path: string; method: string; body: unknown }

function calls(fetchMock: ReturnType<typeof mockFetch>): Call[] {
  return fetchMock.mock.calls.map(([path, init]) => {
    const req = init as RequestInit
    return {
      path: path as string,
      method: req.method as string,
      body: req.body === undefined ? undefined : (JSON.parse(req.body as string) as unknown),
    }
  })
}

afterEach(() => vi.unstubAllGlobals())

describe("GM world requests on the wire", () => {
  it("encodes optional geography and language filters only when given", async () => {
    const fetchMock = mockFetch([])
    const m = api.master

    await m.getLibraryTemplates("politics")
    await m.getLibraryTemplates("politics", "north coast")
    await m.getWorlds()
    await m.getWorlds("ru")
    await m.getWorldManifest("w1")
    await m.getWorldManifest("w1", "en")

    expect(calls(fetchMock).map((c) => c.path)).toEqual([
      "/api/master/library/politics",
      "/api/master/library/politics?geography=north%20coast",
      "/api/master/worlds",
      "/api/master/worlds?lang=ru",
      "/api/master/worlds/w1/manifest",
      "/api/master/worlds/w1/manifest?lang=en",
    ])
    expect(calls(fetchMock).every((c) => c.method === "GET" && c.body === undefined)).toBe(true)
  })

  it("routes world and layer-file operations with the right methods, encoding file names", async () => {
    const fetchMock = mockFetch()
    const m = api.master
    const world = { id: "w2", name: "World" } as never

    await m.assembleWorld({ id: "w2" } as never)
    await m.getWorld("w1")
    await m.forkLayer("w1", "ecology")
    await m.getLayerFiles("w1", "ecology")
    await m.getLayerFile("w1", "ecology", "monsters/a b.yaml")
    await m.updateLayerFile("w1", "ecology", "monsters/a b.yaml", { content: "x: 1" } as never)
    await m.createWorld(world)
    await m.updateWorld("w2", world)
    await m.forkWorld("w1", { new_id: "w3" } as never)
    await m.deleteWorld("w3")
    await m.getRefs("w1", "items")

    expect(calls(fetchMock)).toEqual([
      { method: "POST", path: "/api/master/worlds/assemble", body: { id: "w2" } },
      { method: "GET", path: "/api/master/worlds/w1", body: undefined },
      { method: "POST", path: "/api/master/worlds/w1/fork/ecology", body: undefined },
      { method: "GET", path: "/api/master/worlds/w1/layers/ecology/files", body: undefined },
      { method: "GET", path: "/api/master/worlds/w1/layers/ecology/files/monsters%2Fa%20b.yaml", body: undefined },
      { method: "PUT", path: "/api/master/worlds/w1/layers/ecology/files/monsters%2Fa%20b.yaml", body: { content: "x: 1" } },
      { method: "POST", path: "/api/master/worlds", body: { id: "w2", name: "World" } },
      { method: "PUT", path: "/api/master/worlds/w2", body: { id: "w2", name: "World" } },
      { method: "POST", path: "/api/master/worlds/w1/fork", body: { new_id: "w3" } },
      { method: "DELETE", path: "/api/master/worlds/w3", body: undefined },
      { method: "GET", path: "/api/master/worlds/w1/refs/items", body: undefined },
    ])
  })

  it("covers entity CRUD on the world entity endpoints", async () => {
    const fetchMock = mockFetch()
    const m = api.master
    const entry = { id: "wolf", name: "Wolf" } as EntityEntry
    const base = "/api/master/worlds/w1/entities/monsters"

    await m.listEntities("w1", "monsters")
    await m.getEntity("w1", "monsters", "wolf")
    await m.createEntity("w1", "monsters", "wolf", entry)
    await m.updateEntity("w1", "monsters", "wolf", entry)
    await m.deleteEntity("w1", "monsters", "wolf")

    expect(calls(fetchMock)).toEqual([
      { method: "GET", path: base, body: undefined },
      { method: "GET", path: `${base}/wolf`, body: undefined },
      { method: "POST", path: `${base}/wolf`, body: entry },
      { method: "PUT", path: `${base}/wolf`, body: entry },
      { method: "DELETE", path: `${base}/wolf`, body: undefined },
    ])
  })
})

describe("GM session requests on the wire", () => {
  it("routes session lifecycle, time, language and save operations", async () => {
    const fetchMock = mockFetch()
    const m = api.master
    const base = "/api/master/sessions"

    await m.getSessions()
    await m.createSession({ world_id: "w1" } as never)
    await m.getSession("s1")
    await m.advanceTime("s1", { hours: 2 } as never)
    await m.setLang("s1", { lang: "ru" } as never)
    await m.getSaves("s1")
    await m.save("s1")
    await m.save("s1", "before boss")
    await m.loadSave("s1", "slot1")
    await m.deleteSave("s1", "slot1")
    await m.deleteSession("s1")

    expect(calls(fetchMock)).toEqual([
      { method: "GET", path: base, body: undefined },
      { method: "POST", path: base, body: { world_id: "w1" } },
      { method: "GET", path: `${base}/s1`, body: undefined },
      { method: "POST", path: `${base}/s1/time/advance`, body: { hours: 2 } },
      { method: "PUT", path: `${base}/s1/lang`, body: { lang: "ru" } },
      { method: "GET", path: `${base}/s1/saves`, body: undefined },
      { method: "POST", path: `${base}/s1/save`, body: undefined },
      { method: "POST", path: `${base}/s1/save?name=before%20boss`, body: undefined },
      { method: "POST", path: `${base}/s1/saves/slot1/load`, body: undefined },
      { method: "DELETE", path: `${base}/s1/saves/slot1`, body: undefined },
      { method: "DELETE", path: `${base}/s1`, body: undefined },
    ])
  })

  it("resolves with the decoded response body", async () => {
    mockFetch({ saves: ["a", "b"] })
    await expect(api.master.getSaves("s1")).resolves.toEqual({ saves: ["a", "b"] })
  })
})
