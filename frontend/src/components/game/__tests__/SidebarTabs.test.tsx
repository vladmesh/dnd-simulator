import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { SidebarTabs } from "../SidebarTabs"
import type { PeacefulAwareness, CombatAwareness, PlayerStatus } from "@/types/game"

// ---------------------------------------------------------------------------
// Mocks — child panels are mocked so we test tab logic, not panel internals
// ---------------------------------------------------------------------------

vi.mock("../Perception", () => ({ Perception: () => <div data-testid="perception-panel">Perception</div> }))
vi.mock("../LocationPanel", () => ({ LocationPanel: () => <div data-testid="location-panel">LocationPanel</div> }))
vi.mock("../PlayerStats", () => ({ PlayerStats: () => <div data-testid="player-stats">PlayerStats</div> }))
vi.mock("../BattleMap", () => ({ BattleMap: () => <div data-testid="battle-map">BattleMap</div> }))
vi.mock("../CombatPanel", () => ({ CombatPanel: () => <div data-testid="combat-panel">CombatPanel</div> }))
vi.mock("../TradePanel", () => ({ TradePanel: () => <div data-testid="trade-panel">TradePanel</div> }))

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
  alignment: "neutral",
  hp: 20,
  max_hp: 20,
  ac: 15,
  gold: 50,
  location_id: "loc_1",
  ability_scores: { str: 16, dex: 12, con: 14, int: 10, wis: 10, cha: 8 },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setState(overrides: Partial<ReturnType<typeof useGameStore.getState>>) {
  useGameStore.setState(overrides)
}

beforeEach(() => {
  useGameStore.setState({
    mode: "peaceful",
    awareness: peacefulAwareness,
    player,
    isMyTurn: true,
    waitingForAction: false,
  })
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SidebarTabs — peaceful mode", () => {
  it("shows Nearby / Location / Character tabs", () => {
    render(<SidebarTabs />)
    expect(screen.getByRole("tab", { name: /nearby/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /location/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /character/i })).toBeInTheDocument()
  })

  it("defaults to Nearby tab — shows Perception and TradePanel", () => {
    render(<SidebarTabs />)
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()
    expect(screen.getByTestId("trade-panel")).toBeInTheDocument()
    expect(screen.queryByTestId("location-panel")).not.toBeInTheDocument()
    expect(screen.queryByTestId("player-stats")).not.toBeInTheDocument()
  })

  it("clicking Location tab shows LocationPanel", async () => {
    const user = userEvent.setup()
    render(<SidebarTabs />)
    await user.click(screen.getByRole("tab", { name: /location/i }))
    expect(screen.getByTestId("location-panel")).toBeInTheDocument()
    expect(screen.queryByTestId("perception-panel")).not.toBeInTheDocument()
  })

  it("clicking Character tab shows PlayerStats", async () => {
    const user = userEvent.setup()
    render(<SidebarTabs />)
    await user.click(screen.getByRole("tab", { name: /character/i }))
    expect(screen.getByTestId("player-stats")).toBeInTheDocument()
    expect(screen.queryByTestId("perception-panel")).not.toBeInTheDocument()
  })
})

describe("SidebarTabs — combat mode", () => {
  beforeEach(() => {
    setState({ mode: "combat", awareness: combatAwareness })
  })

  it("shows Map / Nearby / Character tabs", () => {
    render(<SidebarTabs />)
    expect(screen.getByRole("tab", { name: /map/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /nearby/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /character/i })).toBeInTheDocument()
  })

  it("defaults to Map tab — shows BattleMap and CombatPanel", () => {
    render(<SidebarTabs />)
    expect(screen.getByTestId("battle-map")).toBeInTheDocument()
    expect(screen.getByTestId("combat-panel")).toBeInTheDocument()
    expect(screen.queryByTestId("perception-panel")).not.toBeInTheDocument()
  })

  it("clicking Nearby tab shows Perception", async () => {
    const user = userEvent.setup()
    render(<SidebarTabs />)
    await user.click(screen.getByRole("tab", { name: /nearby/i }))
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()
    expect(screen.queryByTestId("battle-map")).not.toBeInTheDocument()
  })
})

describe("SidebarTabs — auto-switch on mode change", () => {
  it("switches to Map when mode changes to combat", () => {
    const { rerender } = render(<SidebarTabs />)
    // Start in peaceful — Nearby is default
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()

    // Mode changes to combat
    setState({ mode: "combat", awareness: combatAwareness })
    rerender(<SidebarTabs />)

    // Map tab should be auto-selected
    expect(screen.getByTestId("battle-map")).toBeInTheDocument()
    expect(screen.queryByTestId("perception-panel")).not.toBeInTheDocument()
  })

  it("switches to Nearby when mode changes back to peaceful", async () => {
    // Start in combat
    setState({ mode: "combat", awareness: combatAwareness })
    const { rerender } = render(<SidebarTabs />)
    expect(screen.getByTestId("battle-map")).toBeInTheDocument()

    // Switch to Nearby tab manually
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /nearby/i }))
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()

    // Mode changes to peaceful
    setState({ mode: "peaceful", awareness: peacefulAwareness })
    rerender(<SidebarTabs />)

    // Nearby is default for peaceful — Perception should show
    expect(screen.getByTestId("perception-panel")).toBeInTheDocument()
    expect(screen.queryByTestId("battle-map")).not.toBeInTheDocument()
  })
})
