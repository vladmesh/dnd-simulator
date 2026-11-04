import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { WsClient } from "@/transport/wsClient"
import type { WsStatus } from "@/transport/wsClient"
import type { ServerMessage } from "@/types/ws"

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static OPEN = 1
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  sent: string[] = []
  closed = false
  url: string
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.closed = true
  }
}

const latest = () => FakeWebSocket.instances.at(-1)!

function trackStatuses(client: WsClient): WsStatus[] {
  const seen: WsStatus[] = []
  client.onStatus((s) => seen.push(s))
  return seen
}

describe("WsClient connection lifecycle", () => {
  let client: WsClient

  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal("WebSocket", FakeWebSocket)
    vi.useFakeTimers()
    client = new WsClient()
  })

  afterEach(() => {
    client.disconnect()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it("builds the session URL from the page host, with a legacy string player id", () => {
    client.connect("s1", "p1")
    const url = new URL(latest().url)
    expect(url.protocol).toBe("ws:")
    expect(url.host).toBe(location.host)
    expect(url.pathname).toBe("/api/ws/s1")
    expect(url.searchParams.get("player_id")).toBe("p1")
    expect(url.searchParams.has("spectate")).toBe(false)
    expect(url.searchParams.has("lang")).toBe(false)
  })

  it("adds no query string without a player, and spectate=true for the master feed", () => {
    client.connect("s1")
    expect(latest().url).toBe(`ws://${location.host}/api/ws/s1`)

    client.connect("s2", { spectate: true })
    const url = new URL(latest().url)
    expect(url.searchParams.get("spectate")).toBe("true")
    expect(url.searchParams.has("player_id")).toBe(false)
  })

  it("reports connecting then connected, and only notifies on actual status changes", () => {
    const seen = trackStatuses(client)
    client.connect("s1", "p1")
    expect(client.getStatus()).toBe("connecting")
    latest().onopen?.()
    latest().onopen?.()
    expect(seen).toEqual(["connecting", "connected"])
    expect(client.getStatus()).toBe("connected")
  })

  it("sends JSON only while the socket is open", () => {
    client.connect("s1", "p1")
    const ws = latest()
    client.send({ type: "end_turn" } as never)
    expect(ws.sent).toEqual([])

    ws.readyState = FakeWebSocket.OPEN
    client.send({ type: "end_turn" } as never)
    expect(ws.sent.map((s) => JSON.parse(s))).toEqual([{ type: "end_turn" }])
  })

  it("dispatches parsed messages to every handler, skips malformed frames, and honours unsubscribe", () => {
    const first: ServerMessage[] = []
    const second: ServerMessage[] = []
    const unsubscribeFirst = client.onMessage((m) => first.push(m))
    client.onMessage((m) => second.push(m))
    client.connect("s1", "p1")

    latest().onmessage?.({ data: "{not json" })
    latest().onmessage?.({ data: JSON.stringify({ type: "game_over" }) })
    unsubscribeFirst()
    latest().onmessage?.({ data: JSON.stringify({ type: "error", message: "x" }) })

    expect(first).toEqual([{ type: "game_over" }])
    expect(second).toEqual([{ type: "game_over" }, { type: "error", message: "x" }])
  })

  it("stops reporting status after the status handler unsubscribes", () => {
    const seen: WsStatus[] = []
    const unsubscribe = client.onStatus((s) => seen.push(s))
    client.connect("s1")
    unsubscribe()
    latest().onopen?.()
    expect(seen).toEqual(["connecting"])
  })

  it("treats close code 4004 as a terminal error with no reconnect", () => {
    client.connect("s1", "p1")
    latest().onclose?.({ code: 4004 })
    expect(client.getStatus()).toBe("error")
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it("reports a socket error as the error status", () => {
    client.connect("s1", "p1")
    latest().onerror?.()
    expect(client.getStatus()).toBe("error")
  })

  it("reconnects with exponential backoff capped at 30s, and resets the delay once connected", () => {
    client.connect("s1", "p1")
    const delays = [1000, 2000, 4000, 8000, 16000, 30000, 30000]
    for (const delay of delays) {
      latest().onclose?.({ code: 1006 })
      expect(client.getStatus()).toBe("disconnected")
      const before = FakeWebSocket.instances.length
      vi.advanceTimersByTime(delay - 1)
      expect(FakeWebSocket.instances).toHaveLength(before)
      vi.advanceTimersByTime(1)
      expect(FakeWebSocket.instances).toHaveLength(before + 1)
    }

    latest().onopen?.()
    latest().onclose?.({ code: 1006 })
    const before = FakeWebSocket.instances.length
    vi.advanceTimersByTime(1000)
    expect(FakeWebSocket.instances).toHaveLength(before + 1)
  })

  it("ignores events from a socket that a reconnect has replaced, and closes it", () => {
    client.connect("s1", "p1")
    const stale = latest()
    const staleOnClose = stale.onclose
    const staleOnOpen = stale.onopen
    const staleOnMessage = stale.onmessage
    const staleOnError = stale.onerror
    const received: ServerMessage[] = []
    client.onMessage((m) => received.push(m))

    client.connect("s1", "p1")
    expect(stale.closed).toBe(true)
    expect(stale.onclose).toBeNull()

    staleOnOpen?.()
    staleOnMessage?.({ data: JSON.stringify({ type: "game_over" }) })
    staleOnError?.()
    staleOnClose?.({ code: 1006 })
    vi.advanceTimersByTime(60_000)

    expect(client.getStatus()).toBe("connecting")
    expect(received).toEqual([])
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it("disconnect closes the socket, cancels a pending reconnect and never reconnects", () => {
    client.connect("s1", "p1")
    latest().onclose?.({ code: 1006 })
    client.disconnect()
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(client.getStatus()).toBe("disconnected")

    client.connect("s1", "p1")
    const ws = latest()
    client.disconnect()
    expect(ws.closed).toBe(true)
    ws.onclose?.({ code: 1000 })
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})
