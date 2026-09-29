import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"

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
import { wsClient } from "@/transport/wsClient"
import { Perception } from "../Perception"
import { NpcInspectModal } from "../NpcInspectModal"
import { SayAction } from "../action-bar/SayAction"
import { MAX_SPEECH_LENGTH, checkSpeech, codePointLength } from "../speechLimit"
import type { NearbyEntity, PeacefulAwareness } from "@/types/game"

const wsSend = wsClient.send as unknown as ReturnType<typeof vi.fn>

// Server bound is Python len (code points). JS .length would count the emoji twice.
const ASTRAL_OK = "😀".repeat(MAX_SPEECH_LENGTH) // 2000 code points, 4000 UTF-16 units
const ASTRAL_OVER = "😀".repeat(MAX_SPEECH_LENGTH + 1)
const COMBINING_OK = "é".repeat(MAX_SPEECH_LENGTH / 2) // 2000 code points
const COMBINING_OVER = "é".repeat(MAX_SPEECH_LENGTH / 2) + "x" // 2001 code points
const PLAIN_OVER = "a".repeat(MAX_SPEECH_LENGTH + 1)

const OVERLONG = [
  ["plain", PLAIN_OVER],
  ["astral", ASTRAL_OVER],
  ["combining", COMBINING_OVER],
] as const
const AT_LIMIT = [
  ["astral", ASTRAL_OK],
  ["combining", COMBINING_OK],
] as const

describe("speech length check", () => {
  it("counts Unicode code points like Python len", () => {
    expect(codePointLength("😀")).toBe(1)
    expect(codePointLength("é")).toBe(2)
    expect(codePointLength(ASTRAL_OK)).toBe(2000)
    expect(ASTRAL_OK.length).toBe(4000)
    expect(codePointLength(COMBINING_OVER)).toBe(2001)
  })

  it("allows exactly 2000 and rejects 2001 code points", () => {
    expect(checkSpeech("a".repeat(2000))).toMatchObject({ canSend: true, tooLong: false })
    expect(checkSpeech(ASTRAL_OK)).toMatchObject({ canSend: true, tooLong: false, length: 2000 })
    expect(checkSpeech(PLAIN_OVER)).toMatchObject({ canSend: false, tooLong: true, length: 2001 })
    expect(checkSpeech(ASTRAL_OVER)).toMatchObject({ canSend: false, tooLong: true })
    expect(checkSpeech(COMBINING_OVER)).toMatchObject({ canSend: false, tooLong: true })
  })

  it("measures the trimmed payload that is actually sent", () => {
    const padded = `   ${"a".repeat(2000)}   `
    expect(checkSpeech(padded)).toMatchObject({ payload: "a".repeat(2000), canSend: true })
    expect(checkSpeech("   ")).toMatchObject({ payload: "", canSend: false, tooLong: false })
  })
})

function expectRejected(input: HTMLInputElement, draft: string, send: { mock: { calls: unknown[] } }) {
  const sendButton = input.parentElement!.querySelector("button")!
  expect(sendButton).toBeDisabled()
  fireEvent.click(sendButton)
  fireEvent.keyDown(input, { key: "Enter" })
  expect(send.mock.calls).toHaveLength(0)
  // The draft is kept, not cleared, and the field stays open.
  expect(input.value).toBe(draft)
  expect(input).toBeInTheDocument()
  const alert = screen.getByRole("alert")
  expect(alert).toHaveTextContent(`${codePointLength(draft)} of 2000`)
  expect(input).toHaveAttribute("aria-invalid", "true")
  expect(input).toHaveAttribute("aria-describedby", alert.id)
}

type SendAction = (name: string, params?: Record<string, unknown>) => void
const makeSend = () => vi.fn<SendAction>()

const t = (key: string, opts?: Record<string, unknown>) => i18n.t(key, opts) as string

describe("SayAction speech bound", () => {
  const open = (send: ReturnType<typeof makeSend>) => {
    render(<SayAction description="say desc" disabled={false} sendAction={send} t={t} />)
    fireEvent.click(screen.getByTitle("say desc"))
    return screen.getByPlaceholderText("Say something...") as HTMLInputElement
  }

  it.each(OVERLONG)("does not send or drop an overlong %s draft", (_, draft) => {
    const send = makeSend()
    const input = open(send)
    fireEvent.change(input, { target: { value: draft } })
    expectRejected(input, draft, send)
  })

  it.each(AT_LIMIT)("sends a %s draft of exactly 2000 code points via Enter", (_, draft) => {
    const send = makeSend()
    const input = open(send)
    fireEvent.change(input, { target: { value: draft } })
    expect(screen.queryByRole("alert")).toBeNull()
    fireEvent.keyDown(input, { key: "Enter" })
    expect(send).toHaveBeenCalledWith("say", { text: draft })
  })

  it("sends the trimmed text via the button", () => {
    const send = makeSend()
    const input = open(send)
    fireEvent.change(input, { target: { value: `  ${ASTRAL_OK}  ` } })
    fireEvent.click(input.parentElement!.querySelector("button")!)
    expect(send).toHaveBeenCalledWith("say", { text: ASTRAL_OK })
  })
})

const goblin: NearbyEntity = { id: "goblin-1", description: "Goblin", lootable: false }

function peaceful(nearby: NearbyEntity[]): PeacefulAwareness {
  return {
    hour: 12, day: 1, month: 1, year: 1, weather: {},
    location_name: "Town", region_name: "Region", nearby,
  }
}

beforeEach(async () => {
  wsSend.mockReset()
  await i18n.changeLanguage("en")
  useGameStore.setState({ mode: "peaceful", awareness: peaceful([goblin]), isMyTurn: true })
})

describe("Perception talk speech bound", () => {
  const open = () => {
    render(<Perception />)
    fireEvent.click(screen.getByRole("button", { name: "Talk to Goblin" }))
    return screen.getByPlaceholderText("Say something...") as HTMLInputElement
  }

  it.each(OVERLONG)("does not send or drop an overlong %s draft", (_, draft) => {
    const input = open()
    fireEvent.change(input, { target: { value: draft } })
    expectRejected(input, draft, wsSend)
  })

  it.each(AT_LIMIT)("sends a %s draft of exactly 2000 code points", (_, draft) => {
    const input = open()
    fireEvent.change(input, { target: { value: draft } })
    fireEvent.click(input.parentElement!.querySelector("button")!)
    expect(wsSend).toHaveBeenCalledWith({
      type: "action", name: "say", params: { target_id: "goblin-1", text: draft },
    })
  })
})

describe("NpcInspectModal talk speech bound", () => {
  const open = (onClose = vi.fn()) => {
    render(<NpcInspectModal entity={goblin} open onClose={onClose} isCombat={false} />)
    fireEvent.click(screen.getByRole("button", { name: "Talk" }))
    return screen.getByPlaceholderText("Say something...") as HTMLInputElement
  }

  it.each(OVERLONG)("does not send, close or drop an overlong %s draft", (_, draft) => {
    const onClose = vi.fn()
    const input = open(onClose)
    fireEvent.change(input, { target: { value: draft } })
    expectRejected(input, draft, wsSend)
    expect(onClose).not.toHaveBeenCalled()
  })

  it.each(AT_LIMIT)("sends a %s draft of exactly 2000 code points via Enter", (_, draft) => {
    const onClose = vi.fn()
    const input = open(onClose)
    fireEvent.change(input, { target: { value: draft } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(wsSend).toHaveBeenCalledWith({
      type: "action", name: "say", params: { target_id: "goblin-1", text: draft },
    })
    expect(onClose).toHaveBeenCalled()
  })

  it("shows the localized Russian message", async () => {
    await i18n.changeLanguage("ru")
    const onClose = vi.fn()
    render(<NpcInspectModal entity={goblin} open onClose={onClose} isCombat={false} />)
    fireEvent.click(screen.getByRole("button", { name: "Говорить" }))
    const input = screen.getByPlaceholderText("Сказать что-то...")
    fireEvent.change(input, { target: { value: ASTRAL_OVER } })
    expect(screen.getByRole("alert")).toHaveTextContent("2001 из 2000")
  })
})
