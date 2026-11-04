import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "@/transport/requestCore"
import { masterContentClient as client } from "@/transport/masterContentClient"
import type { CatalogEntry } from "@/types/api"

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

const entry = { id: "longsword", name: "Longsword", price: 15 } as unknown as CatalogEntry

type Case = [string, () => Promise<unknown>, string, string, unknown]

const cases: Case[] = [
  ["schema list", () => client.getSchemas(), "GET", "/api/master/schemas", undefined],
  ["schema", () => client.getSchema("npc"), "GET", "/api/master/schemas/npc", undefined],
  ["catalog list", () => client.listCatalog("items"), "GET", "/api/master/catalogs/items", undefined],
  ["catalog entry", () => client.getCatalogEntry("items", "longsword"), "GET", "/api/master/catalogs/items/longsword", undefined],
  ["create catalog entry", () => client.createCatalogEntry("items", "longsword", entry), "POST", "/api/master/catalogs/items/longsword", entry],
  ["update catalog entry", () => client.updateCatalogEntry("items", "longsword", entry), "PUT", "/api/master/catalogs/items/longsword", entry],
  ["delete catalog entry", () => client.deleteCatalogEntry("items", "longsword"), "DELETE", "/api/master/catalogs/items/longsword", undefined],
]

describe("masterContentClient on the wire", () => {
  it.each(cases)("%s", async (_name, call, method, path, body) => {
    const fetchMock = mockFetch({ marker: path })
    await expect(call()).resolves.toEqual({ marker: path })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(sent(fetchMock)).toEqual({ path, method, body })
  })

  it("rejects a validation failure with field-level detail", async () => {
    const detail = [{ loc: ["body", "price"], msg: "must be >= 0" }]
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422, text: async () => JSON.stringify({ detail }) }))
    const error = await client.createCatalogEntry("items", "longsword", entry).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).detailMessage()).toBe("price: must be >= 0")
  })
})
