import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "@/transport/requestCore"
import { masterSessionClient as client } from "@/transport/masterSessionClient"
import type { AdvanceTimeRequest, CreateSessionRequest, SetLangRequest } from "@/types/api"

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

const create = { world_id: "w" } as unknown as CreateSessionRequest
const advance = { hours: 8 } as unknown as AdvanceTimeRequest
const lang = { lang: "en" } as unknown as SetLangRequest

type Case = [string, () => Promise<unknown>, string, string, unknown]

const cases: Case[] = [
  ["session list", () => client.getSessions(), "GET", "/api/master/sessions", undefined],
  ["create session", () => client.createSession(create), "POST", "/api/master/sessions", create],
  ["session state", () => client.getSession("s1"), "GET", "/api/master/sessions/s1", undefined],
  ["delete session", () => client.deleteSession("s1"), "DELETE", "/api/master/sessions/s1", undefined],
  ["advance time", () => client.advanceTime("s1", advance), "POST", "/api/master/sessions/s1/time/advance", advance],
  ["set language", () => client.setLang("s1", lang), "PUT", "/api/master/sessions/s1/lang", lang],
  ["save list", () => client.getSaves("s1"), "GET", "/api/master/sessions/s1/saves", undefined],
  ["unnamed save", () => client.save("s1"), "POST", "/api/master/sessions/s1/save", undefined],
  ["named save", () => client.save("s1", "камера & ключ"), "POST", `/api/master/sessions/s1/save?name=${encodeURIComponent("камера & ключ")}`, undefined],
  ["load save", () => client.loadSave("s1", "auto"), "POST", "/api/master/sessions/s1/saves/auto/load", undefined],
  ["delete save", () => client.deleteSave("s1", "auto"), "DELETE", "/api/master/sessions/s1/saves/auto", undefined],
]

describe("masterSessionClient on the wire", () => {
  it.each(cases)("%s", async (_name, call, method, path, body) => {
    const fetchMock = mockFetch({ marker: path })
    await expect(call()).resolves.toEqual({ marker: path })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(sent(fetchMock)).toEqual({ path, method, body })
  })

  it("sends JSON content type on every request", async () => {
    const fetchMock = mockFetch({})
    await client.advanceTime("s1", advance)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.headers).toEqual({ "Content-Type": "application/json" })
  })

  it("rejects with ApiError keeping a non-JSON error body as text", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 502, text: async () => "Bad Gateway" }))
    const error = await client.getSessions().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(502)
    expect((error as ApiError).body).toBe("Bad Gateway")
  })
})
