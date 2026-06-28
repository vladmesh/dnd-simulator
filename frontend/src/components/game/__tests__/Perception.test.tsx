import { render, screen } from "@testing-library/react"
import { describe, it, expect, beforeEach, vi } from "vitest"
import "@/i18n"

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
import { Perception } from "../Perception"
import type { NearbyEntity, PeacefulAwareness } from "@/types/game"

function makeAwareness(nearby: NearbyEntity[]): PeacefulAwareness {
  return {
    hour: 12,
    day: 1,
    month: 1,
    year: 1,
    weather: {},
    location_name: "Town",
    region_name: "Region",
    nearby,
  }
}

beforeEach(() => {
  useGameStore.setState({
    mode: "explore",
    awareness: null,
    isMyTurn: true,
  })
})

describe("Perception — corpse/lootable entities hide Attack/Talk", () => {
  it("hides Attack and Talk for a lootable (corpse/container) entity", () => {
    useGameStore.setState({
      awareness: makeAwareness([
        { id: "goblin-1", description: "Dead Goblin", lootable: true },
      ]),
    })

    render(<Perception />)

    expect(screen.queryByText("Attack")).not.toBeInTheDocument()
    expect(screen.queryByText("Talk")).not.toBeInTheDocument()
  })

  it("shows Attack and Talk for a living (non-lootable) entity", () => {
    useGameStore.setState({
      awareness: makeAwareness([
        { id: "goblin-2", description: "Goblin", lootable: false },
      ]),
    })

    render(<Perception />)

    expect(screen.getByText("Attack")).toBeInTheDocument()
    expect(screen.getByText("Talk")).toBeInTheDocument()
  })
})
