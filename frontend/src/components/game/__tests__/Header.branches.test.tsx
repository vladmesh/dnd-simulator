import { act, cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router"
import i18n from "@/i18n"

// Header uses the store/WS connection, not REST; keep the API isolated too.
vi.mock("@/transport/apiClient", () => ({ api: {} }))

// Register before importing the store, just as in Header.test.tsx.
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
import type { PlayerStatus } from "@/types/game"
import { Header } from "../Header"

const player: PlayerStatus = {
  player_id: "p1",
  name: "Aria",
  race: "elf",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "neutral",
  hp: 20,
  max_hp: 20,
  ac: 16,
  gold: 0,
  location_id: "village",
  ability_scores: { str: 16, dex: 12, con: 14, int: 10, wis: 10, cha: 10 },
}

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={["/game/s1"]}>
      <Routes>
        <Route path="/game/:sessionId" element={<Header />} />
        <Route path="/" element={<h1>Session setup</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
  useGameStore.setState(useGameStore.getInitialState(), true)
  useGameStore.setState({ player })
})

afterEach(async () => {
  cleanup()
  vi.restoreAllMocks()
  useGameStore.setState(useGameStore.getInitialState(), true)
  await i18n.changeLanguage("en")
  localStorage.removeItem("i18n_lang")
})

describe("Header uncovered branches", () => {
  it("has no header or controls while the player has not loaded", () => {
    useGameStore.setState({ player: null })
    renderHeader()

    expect(screen.queryByRole("banner")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByText("Aria")).not.toBeInTheDocument()
    expect(wsClient.disconnect).not.toHaveBeenCalled()
  })

  it("shows player and location data and removes optional data when cleared", () => {
    useGameStore.setState({
      wsStatus: "connected",
      location: {
        current_location: "Oak Village",
        current_location_id: "village",
        description: "A quiet village",
        region_id: "valley",
        paths: [],
      },
      // Clock formatting itself is already covered by Header.test.tsx.
      gameTime: { year: 1490, month: 6, day: 1, hour: 12, minute: 30 },
    })
    renderHeader()

    expect(screen.getByRole("banner")).toBeInTheDocument()
    expect(screen.getByText("Aria")).toBeVisible()
    expect(screen.getByText("20/20")).toBeVisible()
    expect(screen.getByText("Oak Village")).toBeVisible()

    act(() => useGameStore.setState({ location: null, gameTime: null }))

    expect(screen.queryByText("Oak Village")).not.toBeInTheDocument()
    expect(screen.queryByText(/^Y\d+ M\d+ D\d+ /)).not.toBeInTheDocument()
    expect(screen.getByText("Aria")).toBeVisible()
  })

  // Exercise the HP thresholds and non-connected status branches using visible
  // HP/controls, without coupling assertions to the decorative color classes.
  it.each([
    { hp: 10, max_hp: 20, wsStatus: "connecting" },
    { hp: 5, max_hp: 20, wsStatus: "error" },
    { hp: 0, max_hp: 0, wsStatus: "disconnected" },
  ] as const)(
    "shows $hp/$max_hp HP and keeps exit available while $wsStatus",
    ({ hp, max_hp, wsStatus }) => {
      useGameStore.setState({ player: { ...player, hp, max_hp }, wsStatus })
      renderHeader()

      expect(screen.getByText(`${hp}/${max_hp}`)).toBeVisible()
      expect(screen.getByRole("button", { name: "Exit session" })).toBeEnabled()
      expect(screen.getByRole("button", { name: "EN" })).toBeEnabled()
      expect(screen.getByRole("button", { name: "RU" })).toBeEnabled()
    },
  )

  it.each(["connected", "error"] as const)(
    "disconnects and returns to setup when exiting a session with status %s",
    async (wsStatus) => {
      const user = userEvent.setup()
      useGameStore.setState({ wsStatus, sessionId: "s1", playerId: "p1" })
      renderHeader()

      await user.click(screen.getByRole("button", { name: "Exit session" }))

      expect(wsClient.disconnect).toHaveBeenCalledExactlyOnceWith()
      expect(await screen.findByRole("heading", { name: "Session setup" })).toBeVisible()
      expect(screen.queryByRole("banner")).not.toBeInTheDocument()
    },
  )

  it("switches the visible exit label to Russian and back to English", async () => {
    const user = userEvent.setup()
    const changeLanguage = vi.spyOn(i18n, "changeLanguage")
    renderHeader()

    await user.click(screen.getByRole("button", { name: "RU" }))

    expect(changeLanguage).toHaveBeenNthCalledWith(1, "ru")
    expect(await screen.findByRole("button", { name: "Выйти из сессии" })).toBeVisible()
    expect(screen.queryByRole("button", { name: "Exit session" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "EN" }))

    expect(changeLanguage).toHaveBeenNthCalledWith(2, "en")
    expect(await screen.findByRole("button", { name: "Exit session" })).toBeVisible()
    expect(screen.queryByRole("button", { name: "Выйти из сессии" })).not.toBeInTheDocument()
    expect(wsClient.disconnect).not.toHaveBeenCalled()
  })
})
