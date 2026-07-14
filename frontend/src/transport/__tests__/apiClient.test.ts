import { describe, it, expect, vi } from "vitest"
import { api, ApiError } from "@/transport/apiClient"

describe("ApiError.detailMessage", () => {
  it("returns a plain string detail as-is", () => {
    expect(new ApiError(400, { detail: "bad request" }).detailMessage()).toBe("bad request")
  })

  it("joins pydantic {loc, msg} error arrays", () => {
    const err = new ApiError(422, {
      detail: [
        { loc: ["body", "name"], msg: "field required" },
        { loc: ["body", "hp"], msg: "must be positive" },
      ],
    })
    expect(err.detailMessage()).toBe("name: field required; hp: must be positive")
  })

  it("stringifies a non-string, non-array detail", () => {
    expect(new ApiError(400, { detail: 42 }).detailMessage()).toBe("42")
  })

  it("falls back to the generic message when there is no detail", () => {
    expect(new ApiError(500, {}).detailMessage()).toBe("API error 500")
    expect(new ApiError(500, "plain text body").detailMessage()).toBe("API error 500")
  })
})

describe("api compatibility facade", () => {
  it("keeps master world, content, session, creature, and save requests on their established wire paths", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] })
    vi.stubGlobal("fetch", fetchMock)

    await api.master.getWorlds("ru")
    await api.master.getSession("s 1")
    await api.master.getCreatures("s 1", { entity_type: "npc", active: false })
    await api.master.getSchema("npc")
    await api.master.save("s 1", "before combat")

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/master/worlds?lang=ru",
      "/api/master/sessions/s 1",
      "/api/master/sessions/s 1/creatures?entity_type=npc&active=false",
      "/api/master/schemas/npc",
      "/api/master/sessions/s 1/save?name=before%20combat",
    ])
    expect(fetchMock.mock.calls[4][1]).toEqual(
      expect.objectContaining({ method: "POST" }),
    )
  })

  it("keeps player requests and typed errors on the shared request core", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () => JSON.stringify({ detail: "invalid character" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(api.player.getStatus("session-1")).rejects.toMatchObject({
      status: 422,
      body: { detail: "invalid character" },
    })
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/player/sessions/session-1/status",
      expect.objectContaining({ method: "GET" }),
    )
  })
})
