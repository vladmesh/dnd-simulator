import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { EventLog } from "../EventLog"
import { EVENT_ICONS } from "@/lib/logProcessing"
import { ICON_MAP } from "@/lib/iconMap"
import type { PerceivedEvent } from "@/types/game"
import type { LogEntry } from "@/store/slices/logSlice"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _nextId = 1

function makeLogEntry(
  eventType: PerceivedEvent["event_type"],
  description: string,
  actorId?: string | null,
  data?: Record<string, unknown>,
): LogEntry {
  return {
    id: _nextId++,
    event: {
      event_type: eventType,
      description,
      actor_id: actorId ?? null,
      data,
    },
  }
}

function makeMoveEntry(actorId: string, distanceFt: number): LogEntry {
  return makeLogEntry("entity_move", `${actorId} moves ${distanceFt} ft`, actorId, {
    distance_ft: distanceFt,
    entity_id: actorId,
  })
}

function setLog(entries: LogEntry[]) {
  useGameStore.setState({ log: entries })
}

beforeEach(() => {
  _nextId = 1
  useGameStore.setState({ log: [] })
})

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

describe("EventLog — icons", () => {
  it("renders an icon element next to attack event description", () => {
    setLog([makeLogEntry("entity_attack", "You attack the goblin", "player_1")])
    render(<EventLog compact onExpand={vi.fn()} />)

    const entry = screen.getByTestId("compact-log")
    // lucide-react icons render as <svg> elements
    const svgs = entry.querySelectorAll("svg")
    expect(svgs.length).toBeGreaterThanOrEqual(1)
    // Description is still visible
    expect(screen.getByText("You attack the goblin")).toBeInTheDocument()
  })

  it("every EVENT_ICONS value resolves to a component in ICON_MAP", () => {
    for (const [eventType, iconName] of Object.entries(EVENT_ICONS)) {
      expect(ICON_MAP[iconName], `ICON_MAP missing entry for icon "${iconName}" (event_type: ${eventType})`).toBeDefined()
    }
  })

  it("entity_lay_on_hands renders a non-null svg icon", () => {
    setLog([makeLogEntry("entity_lay_on_hands", "Paladin heals 5 HP", "paladin_1")])
    render(<EventLog compact onExpand={vi.fn()} />)

    const entry = screen.getByTestId("compact-log")
    const svgs = entry.querySelectorAll("svg")
    expect(svgs.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Paladin heals 5 HP")).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Turn headers
// ---------------------------------------------------------------------------

describe("EventLog — turn headers", () => {
  it("renders turn header separators between different actors in combat", () => {
    setLog([
      makeLogEntry("combat_started", "Combat!", null),
      makeLogEntry("entity_attack", "A attacks B", "actor_a"),
      makeLogEntry("entity_attack", "B attacks A", "actor_b"),
    ])
    render(<EventLog compact onExpand={vi.fn()} />)

    const headers = screen.getAllByTestId("turn-header")
    expect(headers.length).toBe(2)
  })
})

// ---------------------------------------------------------------------------
// Aggregated moves
// ---------------------------------------------------------------------------

describe("EventLog — aggregated moves", () => {
  it("renders 3 consecutive moves as a single collapsed summary", () => {
    setLog([
      makeMoveEntry("goblin_1", 5),
      makeMoveEntry("goblin_1", 10),
      makeMoveEntry("goblin_1", 10),
    ])
    render(<EventLog compact onExpand={vi.fn()} />)

    // Should show aggregated summary with total distance
    expect(screen.getByText(/25/)).toBeInTheDocument()
    // Individual move descriptions should NOT be visible (collapsed)
    expect(screen.queryByText("goblin_1 moves 5 ft")).not.toBeInTheDocument()
  })

  it("expands aggregated move to show individual entries on click", async () => {
    const user = userEvent.setup()
    setLog([
      makeMoveEntry("goblin_1", 5),
      makeMoveEntry("goblin_1", 10),
      makeMoveEntry("goblin_1", 10),
    ])
    render(<EventLog compact onExpand={vi.fn()} />)

    const expandBtn = screen.getByTestId("aggregated-move-expand")
    await user.click(expandBtn)

    // After expanding, individual entries should be visible
    expect(screen.getByText("goblin_1 moves 5 ft")).toBeInTheDocument()
    // Two entries with 10 ft distance
    expect(screen.getAllByText("goblin_1 moves 10 ft")).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// Compact mode processing
// ---------------------------------------------------------------------------

describe("EventLog — compact mode uses processing", () => {
  it("shows icons and colors in compact mode", () => {
    setLog([
      makeLogEntry("entity_say", "Hello there", "npc_1"),
      makeLogEntry("entity_attack", "You attack", "player_1"),
    ])
    render(<EventLog compact onExpand={vi.fn()} />)

    const log = screen.getByTestId("compact-log")
    // Both entries should have icons (svg elements)
    const svgs = log.querySelectorAll("svg")
    expect(svgs.length).toBeGreaterThanOrEqual(2)
  })
})

// ---------------------------------------------------------------------------
// Full mode with many entries
// ---------------------------------------------------------------------------

describe("EventLog — full mode", () => {
  it("renders 200+ mixed entries without crashing", () => {
    const entries: LogEntry[] = []
    for (let i = 0; i < 200; i++) {
      if (i === 50) {
        entries.push(makeLogEntry("combat_started", "Combat!", null))
      } else if (i === 150) {
        entries.push(makeLogEntry("combat_ended", "Combat ended", null))
      } else if (i % 5 === 0) {
        entries.push(makeMoveEntry("goblin_1", 5))
        entries.push(makeMoveEntry("goblin_1", 10))
      } else {
        entries.push(makeLogEntry("entity_say", `Event ${i}`, `actor_${i % 3}`))
      }
    }
    setLog(entries)

    // Should not throw
    expect(() => render(<EventLog />)).not.toThrow()
  })
})
