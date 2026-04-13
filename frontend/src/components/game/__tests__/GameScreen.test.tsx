import { render, screen, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { GameScreen } from "../GameScreen"
import type { PeacefulAwareness, CombatAwareness, PlayerStatus, PerceivedEvent } from "@/types/game"

// ---------------------------------------------------------------------------
// Mocks — child panels are mocked so we test layout structure, not panel internals
// ---------------------------------------------------------------------------

vi.mock("../Perception", () => ({ Perception: () => <div data-testid="perception-panel">Perception</div> }))
vi.mock("../LocationPanel", () => ({ LocationPanel: () => <div data-testid="location-panel">LocationPanel</div> }))
vi.mock("../PlayerStats", () => ({ PlayerStats: () => <div data-testid="player-stats">PlayerStats</div> }))
vi.mock("../BattleMap", () => ({ BattleMap: () => <div data-testid="battle-map">BattleMap</div> }))
vi.mock("../CombatPanel", () => ({ CombatPanel: () => <div data-testid="combat-panel">CombatPanel</div> }))
vi.mock("../TradePanel", () => ({ TradePanel: () => <div data-testid="trade-panel">TradePanel</div> }))
vi.mock("../ActionBar", () => ({ ActionBar: () => <div data-testid="action-bar">ActionBar</div> }))
vi.mock("../Header", () => ({ Header: () => <div data-testid="header">Header</div> }))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const peacefulAwareness: PeacefulAwareness = {
  hour: 10,
  day: 1,
  month: 1,
  year: 1,
  weather: {},
  location_name: "Town Square",
  region_name: "Valley",
  nearby: [{ id: "npc_1", description: "Guard" }],
  paths: [{ location_id: "loc_2", target_name: "Forest", distance_m: 200 }],
}

const combatAwareness: CombatAwareness = {
  self_hp: 20,
  self_max_hp: 20,
  self_ac: 15,
  self_speed: 30,
  self_weapon: "Sword",
  self_weapon_damage: "1d8",
  nearby: [{ id: "goblin_1", description: "Goblin", distance_ft: 10, direction: "N" }],
  round_number: 1,
}

const player: PlayerStatus = {
  player_id: "p1",
  name: "Hero",
  race: "human",
  char_class: "fighter",
  level: 1,
  experience: 0,
  level_up_available: false,
  xp_to_next_level: 300,
  alignment: "neutral",
  hp: 20,
  max_hp: 20,
  ac: 15,
  gold: 50,
  location_id: "loc_1",
  ability_scores: { str: 16, dex: 12, con: 14, int: 10, wis: 10, cha: 8 },
}

function makeLogEntries(count: number): { id: number; event: PerceivedEvent }[] {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    event: { event_type: "entity_say", description: `Event ${i + 1}` } as PerceivedEvent,
  }))
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderGameScreen() {
  // Mock connect/disconnect so they don't try to open WebSocket
  useGameStore.setState({
    connect: vi.fn() as unknown as typeof useGameStore.getState.prototype.connect,
    disconnect: vi.fn(),
    wsStatus: "connected",
  })

  return render(
    <MemoryRouter initialEntries={["/play/test-session"]}>
      <Routes>
        <Route path="/play/:sessionId" element={<GameScreen />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  useGameStore.setState({
    mode: "peaceful",
    awareness: peacefulAwareness,
    player,
    isMyTurn: true,
    waitingForAction: false,
    log: [],
    lastError: null,
    gameOver: false,
    wsStatus: "connected",
  })
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GameScreen — dashboard layout", () => {
  it("shows all three panels simultaneously (no tabs)", () => {
    renderGameScreen()
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()
    expect(screen.getByTestId("player-stats")).toBeInTheDocument()
    expect(screen.getByTestId("location-panel")).toBeInTheDocument()
  })

  it("does not render SidebarTabs", () => {
    renderGameScreen()
    // No tab role elements for switching panels
    expect(screen.queryByRole("tab")).not.toBeInTheDocument()
    // No tablist
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument()
  })

  it("shows compact log with recent events", () => {
    useGameStore.setState({ log: makeLogEntries(10) })
    renderGameScreen()
    // Last event should be visible
    expect(screen.getByText("Event 10")).toBeInTheDocument()
    // Compact log doesn't show all events — early ones may be cut off
    // (the compact log shows last N, exact N is implementation detail)
  })

  it("shows trade panel alongside perception in peaceful mode", () => {
    renderGameScreen()
    expect(screen.getByTestId("trade-panel")).toBeInTheDocument()
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()
  })
})

describe("GameScreen — combat mode", () => {
  beforeEach(() => {
    useGameStore.setState({ mode: "combat", awareness: combatAwareness })
  })

  it("shows BattleMap and CombatPanel in combat", () => {
    renderGameScreen()
    expect(screen.getByTestId("battle-map")).toBeInTheDocument()
    expect(screen.getByTestId("combat-panel")).toBeInTheDocument()
  })

  it("hides LocationPanel and shows BattleMap in right column during combat", () => {
    renderGameScreen()
    expect(screen.getByTestId("player-stats")).toBeInTheDocument()
    // LocationPanel replaced by BattleMap in right column
    expect(screen.queryByTestId("location-panel")).not.toBeInTheDocument()
    expect(screen.getByTestId("battle-map")).toBeInTheDocument()
  })

  it("left column has only CombatPanel (no BattleMap) during combat", () => {
    renderGameScreen()
    const combatPanel = screen.getByTestId("combat-panel")
    const battleMap = screen.getByTestId("battle-map")
    // CombatPanel and BattleMap should be in different columns (not siblings)
    expect(combatPanel.parentElement).not.toBe(battleMap.parentElement)
  })
})

describe("GameScreen — log expand overlay", () => {
  beforeEach(() => {
    useGameStore.setState({ log: makeLogEntries(10) })
  })

  it("compact log has an expand button", () => {
    renderGameScreen()
    expect(screen.getByTestId("log-expand-btn")).toBeInTheDocument()
  })

  it("clicking expand shows overlay with full log", async () => {
    const user = userEvent.setup()
    renderGameScreen()
    await user.click(screen.getByTestId("log-expand-btn"))
    expect(screen.getByTestId("log-overlay")).toBeInTheDocument()
  })

  it("close button dismisses overlay", async () => {
    const user = userEvent.setup()
    renderGameScreen()
    await user.click(screen.getByTestId("log-expand-btn"))
    expect(screen.getByTestId("log-overlay")).toBeInTheDocument()

    await user.click(screen.getByTestId("log-overlay-close"))
    expect(screen.queryByTestId("log-overlay")).not.toBeInTheDocument()
  })

  it("Escape key dismisses overlay", async () => {
    const user = userEvent.setup()
    renderGameScreen()
    await user.click(screen.getByTestId("log-expand-btn"))
    expect(screen.getByTestId("log-overlay")).toBeInTheDocument()

    fireEvent.keyDown(document, { key: "Escape" })
    expect(screen.queryByTestId("log-overlay")).not.toBeInTheDocument()
  })
})
