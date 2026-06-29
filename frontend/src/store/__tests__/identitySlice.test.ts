import { describe, it, expect, beforeEach, vi } from "vitest"

// Mock wsClient BEFORE the store imports it (connectionSlice subscribes at init)
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
import { loadIdentity } from "@/store/slices/identitySlice"

beforeEach(() => {
  localStorage.clear()
  useGameStore.setState({ userId: null, role: null })
})

describe("identity slice", () => {
  it("setIdentity updates the store", () => {
    useGameStore.getState().setIdentity("alice", "dm")
    expect(useGameStore.getState().userId).toBe("alice")
    expect(useGameStore.getState().role).toBe("dm")
  })

  it("persists identity to localStorage and rehydrates on reload", () => {
    useGameStore.getState().setIdentity("alice", "dm")
    // A reload re-inits the slice from localStorage; loadIdentity is that path.
    expect(loadIdentity()).toEqual({ userId: "alice", role: "dm" })
  })

  it("loadIdentity returns nulls when nothing persisted", () => {
    expect(loadIdentity()).toEqual({ userId: null, role: null })
  })
})
