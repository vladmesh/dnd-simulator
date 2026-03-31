import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
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
import { BudgetDisplay } from "../BudgetDisplay"
import type { TurnBudget, CombatAwareness } from "@/types/game"

const fullBudget: TurnBudget = {
  actions: 1,
  bonus_actions: 1,
  movement_remaining: 30,
  reaction: 1,
}

beforeEach(() => {
  vi.clearAllMocks()
  useGameStore.setState({
    mode: "combat",
    awareness: null,
  })
})

describe("BudgetDisplay — disengage indicator", () => {
  it("shows disengage indicator when is_disengaging is true in awareness", () => {
    const awareness: CombatAwareness = {
      self_hp: 20,
      self_max_hp: 20,
      self_ac: 15,
      self_speed: 30,
      self_weapon: "Sword",
      self_weapon_damage: "1d8",
      self_conditions: [],
      nearby: [],
      round_number: 1,
      available_actions: [],
      available_items: [],
      is_disengaging: true,
    }
    useGameStore.setState({ mode: "combat", awareness })

    render(<BudgetDisplay budget={fullBudget} />)

    expect(screen.getByTestId("disengage-indicator")).toBeTruthy()
  })

  it("does not show disengage indicator when is_disengaging is false", () => {
    const awareness: CombatAwareness = {
      self_hp: 20,
      self_max_hp: 20,
      self_ac: 15,
      self_speed: 30,
      self_weapon: "Sword",
      self_weapon_damage: "1d8",
      self_conditions: [],
      nearby: [],
      round_number: 1,
      available_actions: [],
      available_items: [],
      is_disengaging: false,
    }
    useGameStore.setState({ mode: "combat", awareness })

    render(<BudgetDisplay budget={fullBudget} />)

    expect(screen.queryByTestId("disengage-indicator")).toBeNull()
  })

  it("does not show disengage indicator when awareness is null", () => {
    useGameStore.setState({ mode: "combat", awareness: null })

    render(<BudgetDisplay budget={fullBudget} />)

    expect(screen.queryByTestId("disengage-indicator")).toBeNull()
  })
})
