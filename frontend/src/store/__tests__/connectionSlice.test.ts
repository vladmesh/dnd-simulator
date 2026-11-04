import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import "@/i18n"

const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))
vi.mock("sonner", () => ({ toast: toastMock }))

import { useGameStore } from "@/store/gameStore"

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static OPEN = 1
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  send() {}
  close() {}
}

const latest = () => FakeWebSocket.instances.at(-1)!

describe("connection slice", () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal("WebSocket", FakeWebSocket)
    vi.useFakeTimers()
    toastMock.success.mockClear()
    toastMock.error.mockClear()
    toastMock.warning.mockClear()
  })

  afterEach(() => {
    useGameStore.getState().disconnect()
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it("connect stores the session and player and opens the player socket; disconnect clears them", () => {
    useGameStore.getState().connect("s1", "p1")
    expect(useGameStore.getState()).toMatchObject({ sessionId: "s1", playerId: "p1", player: null })
    expect(new URL(latest().url).searchParams.get("player_id")).toBe("p1")

    useGameStore.getState().disconnect()
    expect(useGameStore.getState()).toMatchObject({ sessionId: null, playerId: null })
  })

  it("connect without a player stores a null player id", () => {
    useGameStore.getState().connect("s1")
    expect(useGameStore.getState().playerId).toBeNull()
  })

  it("mirrors socket status into the store and toasts connect, error and drop transitions", () => {
    useGameStore.getState().connect("s1", "p1")
    vi.runOnlyPendingTimers()
    expect(useGameStore.getState().wsStatus).toBe("connecting")
    expect(toastMock.success).not.toHaveBeenCalled()

    latest().onopen?.()
    vi.runOnlyPendingTimers()
    expect(useGameStore.getState().wsStatus).toBe("connected")
    expect(toastMock.success).toHaveBeenCalledTimes(1)

    latest().onclose?.({ code: 1006 })
    vi.advanceTimersByTime(0)
    expect(useGameStore.getState().wsStatus).toBe("disconnected")
    expect(toastMock.warning).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(1000) // reconnect attempt → connecting
    vi.runOnlyPendingTimers()
    expect(FakeWebSocket.instances).toHaveLength(2)
    expect(useGameStore.getState().wsStatus).toBe("connecting")

    latest().onerror?.()
    vi.runOnlyPendingTimers()
    expect(useGameStore.getState().wsStatus).toBe("error")
    expect(toastMock.error).toHaveBeenCalledTimes(1)
    expect(toastMock.warning).toHaveBeenCalledTimes(1)
  })

  it("does not warn about a drop when the socket was never connected", () => {
    useGameStore.getState().connect("s1", "p1")
    latest().onclose?.({ code: 1006 })
    vi.advanceTimersByTime(0)
    expect(useGameStore.getState().wsStatus).toBe("disconnected")
    expect(toastMock.warning).not.toHaveBeenCalled()
  })

  it("routes each server message type to its handler and ignores unknown types", () => {
    const handlers = {
      onTurn: vi.fn(),
      onActionResult: vi.fn(),
      onRoundResult: vi.fn(),
      onError: vi.fn(),
      onGameOver: vi.fn(),
      onReactionPrompt: vi.fn(),
    }
    const original = { ...useGameStore.getState() }
    useGameStore.getState().connect("s1", "p1")
    useGameStore.setState(handlers)
    try {
      const messages = [
        { type: "turn", n: 1 },
        { type: "action_result", n: 2 },
        { type: "round_result", n: 3 },
        { type: "error", n: 4 },
        { type: "game_over" },
        { type: "reaction_prompt", n: 6 },
        { type: "something_new" },
      ]
      for (const msg of messages) latest().onmessage?.({ data: JSON.stringify(msg) })
      expect(handlers.onTurn).not.toHaveBeenCalled() // dispatch is deferred
      vi.runOnlyPendingTimers()

      expect(handlers.onTurn).toHaveBeenCalledWith(messages[0])
      expect(handlers.onActionResult).toHaveBeenCalledWith(messages[1])
      expect(handlers.onRoundResult).toHaveBeenCalledWith(messages[2])
      expect(handlers.onError).toHaveBeenCalledWith(messages[3])
      expect(handlers.onGameOver).toHaveBeenCalledTimes(1)
      expect(handlers.onReactionPrompt).toHaveBeenCalledWith(messages[5])
      for (const fn of Object.values(handlers)) expect(fn).toHaveBeenCalledTimes(1)
    } finally {
      useGameStore.setState({
        onTurn: original.onTurn,
        onActionResult: original.onActionResult,
        onRoundResult: original.onRoundResult,
        onError: original.onError,
        onGameOver: original.onGameOver,
        onReactionPrompt: original.onReactionPrompt,
      })
    }
  })
})
