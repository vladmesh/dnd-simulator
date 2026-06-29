import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, beforeEach, vi } from "vitest"
import { MemoryRouter, Routes, Route } from "react-router"
import "@/i18n"

// Mock wsClient BEFORE the store (LandingPage reads identity from it) subscribes
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

import { LandingPage } from "../LandingPage"
import { useGameStore } from "@/store/gameStore"

function setup() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/play" element={<div>SetupScreen</div>} />
        <Route path="/master" element={<div>MasterScreen</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
  useGameStore.setState({ userId: null, role: null })
})

describe("LandingPage", () => {
  it("renders Play and Dungeon Master cards", () => {
    setup()
    expect(screen.getByRole("link", { name: /play/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /dungeon master/i })).toBeInTheDocument()
  })

  it("navigates to /play when Play is clicked", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole("link", { name: /play/i }))
    expect(screen.getByText("SetupScreen")).toBeInTheDocument()
  })

  it("navigates to /master when Dungeon Master is clicked", async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole("link", { name: /dungeon master/i }))
    expect(screen.getByText("MasterScreen")).toBeInTheDocument()
  })

  it("entering a username and picking a role sets identity in the store", async () => {
    const user = userEvent.setup()
    setup()

    await user.type(screen.getByRole("textbox", { name: /name/i }), "alice")
    await user.selectOptions(screen.getByRole("combobox", { name: /role/i }), "dm")

    expect(useGameStore.getState().userId).toBe("alice")
    expect(useGameStore.getState().role).toBe("dm")
  })
})
