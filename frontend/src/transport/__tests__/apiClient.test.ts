import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"

// Mock wsClient BEFORE the store (imported transitively by apiClient) subscribes
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

import { api } from "@/transport/apiClient"
import { useGameStore } from "@/store/gameStore"

function okFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: "ok" }),
    text: () => Promise.resolve(""),
  })
}

function lastHeaders(fetchMock: ReturnType<typeof okFetch>): Record<string, string> {
  const opts = fetchMock.mock.calls[0][1] as RequestInit
  return opts.headers as Record<string, string>
}

beforeEach(() => {
  localStorage.clear()
  useGameStore.setState({ userId: null, role: null })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("apiClient identity headers", () => {
  it("sends X-User-Id and X-Role when identity is set", async () => {
    useGameStore.getState().setIdentity("alice", "dm")
    const fetchMock = okFetch()
    vi.stubGlobal("fetch", fetchMock)

    await api.health()

    const headers = lastHeaders(fetchMock)
    expect(headers["X-User-Id"]).toBe("alice")
    expect(headers["X-Role"]).toBe("dm")
  })

  it("omits identity headers when identity is unset", async () => {
    const fetchMock = okFetch()
    vi.stubGlobal("fetch", fetchMock)

    await api.health()

    const headers = lastHeaders(fetchMock)
    expect(headers["X-User-Id"]).toBeUndefined()
    expect(headers["X-Role"]).toBeUndefined()
  })
})
