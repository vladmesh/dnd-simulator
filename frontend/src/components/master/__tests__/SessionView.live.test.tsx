import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"

// Each new WsClient registers itself so the test can drive its message stream.
// Defined inside vi.hoisted so the mock factory (hoisted above imports) can reach it.
const { wsInstances, MockWsClient } = vi.hoisted(() => {
  const instances: Cls[] = []
  class Cls {
    connect = vi.fn()
    disconnect = vi.fn()
    onStatus = vi.fn(() => vi.fn())
    getStatus = vi.fn(() => "disconnected")
    send = vi.fn()
    handlers = new Set<(m: unknown) => void>()
    onMessage = vi.fn((h: (m: unknown) => void) => {
      this.handlers.add(h)
      return () => this.handlers.delete(h)
    })
    emit(m: unknown) {
      this.handlers.forEach((h) => h(m))
    }
    constructor() {
      instances.push(this)
    }
  }
  return { wsInstances: instances, MockWsClient: Cls }
})

type MockWsClient = InstanceType<typeof MockWsClient>

vi.mock("@/transport/wsClient", () => ({
  WsClient: MockWsClient,
  wsClient: new MockWsClient(),
}))

vi.mock("@/transport/apiClient", () => ({
  api: {
    master: {
      getSession: vi.fn(),
      getCreatures: vi.fn(),
      deleteCreature: vi.fn(),
      setBrain: vi.fn(),
    },
  },
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import { SessionView } from "../SessionView"
import { api } from "@/transport/apiClient"
import type { WorldStateResponse } from "@/types/api"

const mockApi = vi.mocked(api.master)

const emptyWorld: WorldStateResponse = {
  session_id: "sess-1",
  time: "Day 1",
  regions: [],
  nations: [],
  settlements: [],
  entities: [],
}

function renderView() {
  return render(
    <MemoryRouter initialEntries={["/master/sess-1"]}>
      <Routes>
        <Route path="/master/:sessionId" element={<SessionView />} />
      </Routes>
    </MemoryRouter>,
  )
}

function lastWs(): MockWsClient {
  return wsInstances[wsInstances.length - 1]
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  wsInstances.length = 0
  mockApi.getSession.mockResolvedValue(emptyWorld)
  mockApi.getCreatures.mockResolvedValue([])
})

describe("SessionView live observe feed", () => {
  it("renders live events without action controls", async () => {
    const user = userEvent.setup()
    renderView()

    await screen.findByText(/Day 1/)
    await user.click(screen.getByRole("button", { name: /live/i }))

    const ws = lastWs()
    expect(ws.connect).toHaveBeenCalledWith("sess-1", { spectate: true })

    act(() => {
      ws.emit({
        type: "turn",
        events: [
          { description: "Goblin attacks Aria", event_type: "entity_attack" },
          { description: "Aria moves north", event_type: "entity_move" },
        ],
      })
    })

    expect(await screen.findByText("Goblin attacks Aria")).toBeInTheDocument()
    expect(screen.getByText("Aria moves north")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^attack$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /end turn/i })).not.toBeInTheDocument()
  })

  it("keeps existing write tabs while adding the live feed", async () => {
    const user = userEvent.setup()
    renderView()

    await screen.findByText(/Day 1/)
    expect(screen.getByRole("button", { name: /^time$/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /^saves$/i })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /live/i }))
    const ws = lastWs()
    act(() => {
      ws.emit({ type: "turn", events: [{ description: "Orc roars", event_type: "custom" }] })
    })

    expect(await screen.findByText("Orc roars")).toBeInTheDocument()
  })

  it("accumulates events across turn and action_result messages in arrival order", async () => {
    const user = userEvent.setup()
    renderView()

    await screen.findByText(/Day 1/)
    await user.click(screen.getByRole("button", { name: /live/i }))
    const ws = lastWs()

    act(() => {
      ws.emit({ type: "turn", events: [{ description: "First event", event_type: "custom" }] })
    })
    act(() => {
      ws.emit({
        type: "action_result",
        events: [{ description: "Second event", event_type: "custom" }],
      })
    })

    expect(await screen.findByText("First event")).toBeInTheDocument()
    expect(screen.getByText("Second event")).toBeInTheDocument()
    const feed = screen.getByTestId("live-feed")
    const text = feed.textContent ?? ""
    expect(text.indexOf("First event")).toBeLessThan(text.indexOf("Second event"))
  })

  it("connects the spectator socket on mount and disconnects on unmount", async () => {
    const user = userEvent.setup()
    const { unmount } = renderView()

    await screen.findByText(/Day 1/)
    await user.click(screen.getByRole("button", { name: /live/i }))
    const ws = lastWs()
    expect(ws.connect).toHaveBeenCalledWith("sess-1", { spectate: true })

    unmount()
    expect(ws.disconnect).toHaveBeenCalled()
  })
})
