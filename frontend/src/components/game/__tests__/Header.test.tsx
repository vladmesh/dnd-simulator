import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"

// Mock wsClient BEFORE store imports it
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
import type { PlayerStatus } from "@/types/game"
import { Header } from "../Header"

const player = { name: "Hero", hp: 10, max_hp: 10 } as unknown as PlayerStatus

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={["/game/s1"]}>
      <Routes>
        <Route path="/game/:sessionId" element={<Header />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  useGameStore.setState({ player, location: null, gameTime: null })
})

describe("Header clock", () => {
  it("shows minutes, so a 24-minute flee moves the clock", () => {
    useGameStore.setState({ gameTime: { year: 1490, month: 6, day: 1, hour: 10, minute: 24 } })
    renderHeader()
    expect(screen.getByText("Y1490 M6 D1 10:24")).toBeInTheDocument()
  })

  it("pads single-digit hours and minutes", () => {
    useGameStore.setState({ gameTime: { year: 1490, month: 6, day: 1, hour: 9, minute: 5 } })
    renderHeader()
    expect(screen.getByText("Y1490 M6 D1 09:05")).toBeInTheDocument()
  })
})
