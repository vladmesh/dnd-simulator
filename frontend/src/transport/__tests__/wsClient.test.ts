import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import i18next from "i18next"
import "@/i18n"
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

function langParam(url: string): string | null {
  return new URL(url).searchParams.get("lang")
}

describe("player WS connection carries the UI language", () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal("WebSocket", FakeWebSocket)
  })

  afterEach(async () => {
    useGameStore.getState().disconnect()
    vi.unstubAllGlobals()
    await i18next.changeLanguage("en")
  })

  it("sends the language chosen on the landing/setup screens, so the first turn is rendered in it", async () => {
    await i18next.changeLanguage("ru")
    useGameStore.getState().connect("s1", "p1")

    const url = FakeWebSocket.instances.at(-1)!.url
    expect(new URL(url).searchParams.get("player_id")).toBe("p1")
    expect(langParam(url)).toBe("ru")
  })

  it("a reconnect sends the language current at reconnect time", async () => {
    vi.useFakeTimers()
    try {
      await i18next.changeLanguage("ru")
      useGameStore.getState().connect("s1", "p1")
      await i18next.changeLanguage("en")

      FakeWebSocket.instances.at(-1)!.onclose?.({ code: 1006 })
      vi.runOnlyPendingTimers()

      expect(FakeWebSocket.instances).toHaveLength(2)
      expect(langParam(FakeWebSocket.instances[1].url)).toBe("en")
    } finally {
      vi.useRealTimers()
    }
  })
})
