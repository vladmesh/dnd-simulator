import { act, cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Link, MemoryRouter, Route, Routes, useNavigate } from "react-router"
import i18n from "@/i18n"
import { api } from "@/transport/apiClient"
import { wsClient } from "@/transport/wsClient"
import { useGameStore } from "@/store/gameStore"
import type { CombatAwareness, PlayerStatus } from "@/types/game"
import { GameScreen } from "../GameScreen"

// Keep the header, action bar, map and inspect dialog real; unrelated panels
// already have layout coverage in GameScreen.test.tsx.
vi.mock("../Perception", () => ({ Perception: () => null }))
vi.mock("../LocationPanel", () => ({ LocationPanel: () => null }))
vi.mock("../PlayerStats", () => ({ PlayerStats: () => null }))
vi.mock("../CombatPanel", () => ({ CombatPanel: () => null }))
vi.mock("../TradePanel", () => ({ TradePanel: () => null, MerchantView: () => null }))
vi.mock("../LootPanel", () => ({ LootPanel: () => null }))
vi.mock("../EventLog", () => ({ EventLog: () => null }))
vi.mock("../LogOverlay", () => ({ LogOverlay: () => null }))
vi.mock("../ReactionPrompt", () => ({ ReactionPrompt: () => null }))

vi.mock("@/transport/apiClient", () => ({
  api: { master: { setLang: vi.fn() } },
}))
vi.mock("@/transport/wsClient", () => ({
  wsClient: { onStatus: vi.fn(), onMessage: vi.fn(), send: vi.fn() },
}))

const player: PlayerStatus = {
  player_id: "branch-player",
  name: "Mira",
  race: "elf",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "neutral",
  hp: 12,
  max_hp: 18,
  ac: 14,
  gold: 20,
  location_id: "square",
  ability_scores: { str: 14, dex: 14, con: 12, int: 10, wis: 12, cha: 10 },
}

const combat: CombatAwareness = {
  self_hp: 12,
  self_max_hp: 18,
  self_ac: 14,
  self_speed: 30,
  self_weapon: "Sword",
  self_weapon_damage: "1d8",
  self_x: 0,
  self_y: 0,
  round_number: 1,
  battle_map_width: 10,
  battle_map_height: 10,
  nearby: [{ id: "scout", description: "Goblin scout", x: 5, y: 5, distance_ft: 5, direction: "NE" }],
}

const initialState = useGameStore.getState()
const connect = vi.fn<typeof initialState.connect>()
const disconnect = vi.fn<typeof initialState.disconnect>()

function Home() {
  const navigate = useNavigate()
  return <><h1>Home</h1><button onClick={() => navigate(-1)}>Back</button></>
}

function renderGame(path = "/play/branch-session") {
  return render(
    <MemoryRouter initialEntries={["/lobby", path]} initialIndex={1}>
      <Link to="/play/next-session">Next session</Link>
      <Routes>
        <Route path="/play/:sessionId?" element={<GameScreen />} />
        <Route path="/" element={<Home />} />
        <Route path="/lobby" element={<h1>Lobby</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(async () => {
  vi.clearAllMocks()
  localStorage.clear()
  await i18n.changeLanguage("en")
  vi.mocked(api.master.setLang).mockResolvedValue({ message: "ok" })
  useGameStore.setState({ ...initialState, connect, disconnect, wsStatus: "connecting" }, true)
})

afterEach(() => {
  cleanup()
  useGameStore.setState(initialState, true)
  localStorage.clear()
})

describe("GameScreen — previously uncovered branches", () => {
  it("waits for initial player data, then updates the header and page title", () => {
    const { unmount } = renderGame()
    expect(screen.getByText("Waiting for turn...")).toBeInTheDocument()
    expect(screen.queryByRole("banner")).not.toBeInTheDocument()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(document.title).toBe("D&D Simulator")
    expect(connect).toHaveBeenCalledExactlyOnceWith("branch-session", undefined)

    act(() => useGameStore.setState({ player, wsStatus: "connected" }))
    expect(within(screen.getByRole("banner")).getByText("Mira")).toBeInTheDocument()
    expect(screen.getByText("12/18")).toBeInTheDocument()
    expect(document.title).toBe("Mira — D&D Simulator")

    act(() => useGameStore.setState({ player: { ...player, name: "Mira the Brave" } }))
    expect(screen.getByText("Mira the Brave")).toBeInTheDocument()
    expect(document.title).toBe("Mira the Brave — D&D Simulator")
    unmount()
    expect(document.title).toBe("D&D Simulator")
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it("reuses the saved player id without reconnecting on store updates", () => {
    localStorage.setItem("player_id:other-session", "wrong-player")
    localStorage.setItem("player_id:branch-session", "returning-player")
    const { unmount } = renderGame()
    expect(connect).toHaveBeenCalledExactlyOnceWith("branch-session", "returning-player")

    act(() => useGameStore.setState({ lastError: "Temporary interruption" }))
    expect(screen.getByText("Temporary interruption")).toBeInTheDocument()
    expect(connect).toHaveBeenCalledOnce()
    expect(disconnect).not.toHaveBeenCalled()
    unmount()
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it("does not connect or send language requests without a session id", () => {
    const { unmount } = renderGame("/play")
    expect(screen.getByText("Waiting for turn...")).toBeInTheDocument()
    expect(connect).not.toHaveBeenCalled()
    expect(api.master.setLang).not.toHaveBeenCalled()
    unmount()
    expect(disconnect).not.toHaveBeenCalled()
  })

  it("disconnects the previous session and uses the next session's saved identity", async () => {
    const user = userEvent.setup()
    localStorage.setItem("player_id:next-session", "next-player")
    const { unmount } = renderGame()
    await user.click(screen.getByRole("link", { name: "Next session" }))

    expect(disconnect).toHaveBeenCalledOnce()
    expect(connect.mock.calls).toEqual([
      ["branch-session", undefined],
      ["next-session", "next-player"],
    ])
    expect(api.master.setLang).toHaveBeenLastCalledWith("next-session", { lang: "en" })
    unmount()
    expect(disconnect).toHaveBeenCalledTimes(2)
  })

  it("shows and clears server errors and game-over notifications", () => {
    renderGame()
    expect(screen.queryByText("GAME OVER")).not.toBeInTheDocument()
    act(() => useGameStore.setState({ lastError: "The bridge is blocked", gameOver: true }))
    expect(screen.getByText("The bridge is blocked")).toBeInTheDocument()
    expect(screen.getByText("GAME OVER")).toBeInTheDocument()

    act(() => useGameStore.setState({ lastError: null, gameOver: false }))
    expect(screen.queryByText("The bridge is blocked")).not.toBeInTheDocument()
    expect(screen.queryByText("GAME OVER")).not.toBeInTheDocument()
    expect(screen.getByText("Waiting for turn...")).toBeInTheDocument()
  })

  it("replaces a permanently failed session with home and disconnects", async () => {
    const user = userEvent.setup()
    renderGame()
    act(() => useGameStore.setState({ wsStatus: "error" }))
    expect(await screen.findByRole("heading", { name: "Home" })).toBeInTheDocument()
    expect(disconnect).toHaveBeenCalledOnce()

    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(screen.getByRole("heading", { name: "Lobby" })).toBeInTheDocument()
    expect(connect).toHaveBeenCalledOnce()
  })

  it("ignores a rejected language sync while the WebSocket session remains usable", async () => {
    vi.mocked(api.master.setLang).mockRejectedValueOnce(new Error("Session is gone"))
    useGameStore.setState({ player, wsStatus: "connected" })
    await act(async () => { renderGame() })

    expect(api.master.setLang).toHaveBeenCalledExactlyOnceWith("branch-session", { lang: "en" })
    expect(screen.getByText("Mira")).toBeInTheDocument()
    expect(screen.queryByText("Session is gone")).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Home" })).not.toBeInTheDocument()
    expect(disconnect).not.toHaveBeenCalled()
  })

  it("opens the clicked map creature's inspect dialog and clears it when closed", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ mode: "combat", awareness: combat, isMyTurn: false })
    renderGame()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Goblin scout" }))

    const dialog = screen.getByRole("dialog", { name: "Goblin scout" })
    expect(within(dialog).getByText("5ft NE")).toBeInTheDocument()
    expect(within(dialog).queryByRole("button", { name: "Attack Goblin scout" })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Close" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Goblin scout" }))
    expect(screen.getByRole("dialog", { name: "Goblin scout" })).toBeInTheDocument()
    expect(wsClient.send).not.toHaveBeenCalled()
  })

  it("disables turn actions while awaiting a response and enables them when ready", async () => {
    const user = userEvent.setup()
    useGameStore.setState({ isMyTurn: true, waitingForAction: true })
    renderGame()
    const endTurn = screen.getByRole("button", { name: "End Turn" })
    expect(endTurn).toBeDisabled()
    await user.click(endTurn)
    expect(wsClient.send).not.toHaveBeenCalled()

    act(() => useGameStore.setState({ waitingForAction: false }))
    expect(endTurn).toBeEnabled()
    await user.click(endTurn)
    expect(wsClient.send).toHaveBeenCalledExactlyOnceWith({
      type: "action", name: "end_turn", params: undefined,
    })
    expect(endTurn).toBeDisabled()
  })
})
