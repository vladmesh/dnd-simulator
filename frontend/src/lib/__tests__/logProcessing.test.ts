import { describe, it, expect } from "vitest"
import {
  processLogEntries,
  EVENT_ICONS,
  EVENT_COLORS,
} from "../logProcessing"
import type { EventType, PerceivedEvent } from "@/types/game"
import type { LogEntry } from "@/store/slices/logSlice"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _nextId = 1

function makeEntry(
  eventType: EventType,
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

function makeMoveEntry(
  actorId: string,
  distanceFt: number,
  description?: string,
): LogEntry {
  return makeEntry(
    "entity_move",
    description ?? `${actorId} moves ${distanceFt} ft`,
    actorId,
    { distance_ft: distanceFt, entity_id: actorId },
  )
}

function makeDashEntry(
  actorId: string,
  distanceFt: number,
  description?: string,
): LogEntry {
  return makeEntry(
    "entity_dash",
    description ?? `${actorId} dashes ${distanceFt} ft`,
    actorId,
    { distance_ft: distanceFt, entity_id: actorId },
  )
}

// ---------------------------------------------------------------------------
// Icon mapping
// ---------------------------------------------------------------------------

describe("EVENT_ICONS", () => {
  const ALL_EVENT_TYPES: EventType[] = [
    "entity_died",
    "entity_say",
    "entity_attack",
    "entity_dodge",
    "entity_flee",
    "entity_move",
    "entity_dash",
    "entity_disengage",
    "entity_bless",
    "entity_use_item",
    "entity_second_wind",
    "entity_equip",
    "entity_unequip",
    "entity_buy",
    "entity_sell",
    "action_error",
    "turn_skipped",
    "combat_started",
    "combat_ended",
    "encounter_spawned",
    "weather_changed",
    "time_advanced",
    "squad_move",
    "squad_combat",
    "squad_materialized",
    "squad_dematerialized",
    "custom",
  ]

  it("maps every EventType to a lucide icon name", () => {
    for (const et of ALL_EVENT_TYPES) {
      expect(EVENT_ICONS[et], `missing icon for ${et}`).toBeDefined()
      expect(typeof EVENT_ICONS[et]).toBe("string")
      expect(EVENT_ICONS[et].length).toBeGreaterThan(0)
    }
  })

  it("maps known types to expected icons", () => {
    expect(EVENT_ICONS["entity_attack"]).toBe("swords")
    expect(EVENT_ICONS["entity_say"]).toBe("message-circle")
    expect(EVENT_ICONS["entity_move"]).toBe("footprints")
    expect(EVENT_ICONS["entity_died"]).toBe("skull")
    expect(EVENT_ICONS["combat_started"]).toBe("flame")
    expect(EVENT_ICONS["weather_changed"]).toBe("cloud-sun")
  })
})

// ---------------------------------------------------------------------------
// Color mapping
// ---------------------------------------------------------------------------

describe("EVENT_COLORS", () => {
  it("maps every EventType to a Tailwind class string", () => {
    const allTypes: EventType[] = [
      "entity_died",
      "entity_say",
      "entity_attack",
      "entity_dodge",
      "entity_flee",
      "entity_move",
      "entity_dash",
      "entity_disengage",
      "entity_bless",
      "entity_use_item",
      "entity_second_wind",
      "entity_equip",
      "entity_unequip",
      "entity_buy",
      "entity_sell",
      "action_error",
      "turn_skipped",
      "combat_started",
      "combat_ended",
      "encounter_spawned",
      "weather_changed",
      "time_advanced",
      "squad_move",
      "squad_combat",
      "squad_materialized",
      "squad_dematerialized",
      "custom",
    ]

    for (const et of allTypes) {
      expect(EVENT_COLORS[et], `missing color for ${et}`).toBeDefined()
      expect(typeof EVENT_COLORS[et]).toBe("string")
      expect(EVENT_COLORS[et].length).toBeGreaterThan(0)
    }
  })
})

// ---------------------------------------------------------------------------
// Move aggregation
// ---------------------------------------------------------------------------

describe("processLogEntries — move aggregation", () => {
  it("aggregates 3 consecutive moves from same actor into one entry with total distance", () => {
    const entries = [
      makeMoveEntry("goblin_1", 5),
      makeMoveEntry("goblin_1", 10),
      makeMoveEntry("goblin_1", 10),
    ]

    const result = processLogEntries(entries)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe("aggregated_move")
    if (result[0].kind === "aggregated_move") {
      expect(result[0].totalDistanceFt).toBe(25)
      expect(result[0].entries).toHaveLength(3)
      expect(result[0].actorId).toBe("goblin_1")
    }
  })

  it("breaks aggregation when actor changes", () => {
    const entries = [
      makeMoveEntry("goblin_1", 5),
      makeMoveEntry("goblin_1", 10),
      makeMoveEntry("goblin_2", 15),
    ]

    const result = processLogEntries(entries)

    // aggregated(goblin_1, 2 moves) + regular(goblin_2)
    expect(result).toHaveLength(2)
    expect(result[0].kind).toBe("aggregated_move")
    if (result[0].kind === "aggregated_move") {
      expect(result[0].actorId).toBe("goblin_1")
      expect(result[0].entries).toHaveLength(2)
      expect(result[0].totalDistanceFt).toBe(15)
    }
    expect(result[1].kind).toBe("event")
  })

  it("breaks aggregation on non-move event from same actor", () => {
    const entries = [
      makeMoveEntry("goblin_1", 5),
      makeEntry("entity_attack", "Goblin attacks", "goblin_1"),
      makeMoveEntry("goblin_1", 10),
    ]

    const result = processLogEntries(entries)

    // regular move, attack, regular move — no aggregation
    expect(result).toHaveLength(3)
    expect(result.every((e) => e.kind === "event")).toBe(true)
  })

  it("includes entity_dash in move aggregation with entity_move", () => {
    const entries = [
      makeMoveEntry("goblin_1", 10),
      makeDashEntry("goblin_1", 15),
    ]

    const result = processLogEntries(entries)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe("aggregated_move")
    if (result[0].kind === "aggregated_move") {
      expect(result[0].totalDistanceFt).toBe(25)
      expect(result[0].entries).toHaveLength(2)
    }
  })

  it("does NOT aggregate a single move — keeps it as a regular event", () => {
    const entries = [makeMoveEntry("goblin_1", 10)]

    const result = processLogEntries(entries)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe("event")
  })
})

// ---------------------------------------------------------------------------
// Turn headers
// ---------------------------------------------------------------------------

describe("processLogEntries — turn headers", () => {
  it("inserts turn headers when actor_id changes during combat", () => {
    const entries = [
      makeEntry("combat_started", "Combat!", null),
      makeEntry("entity_attack", "A attacks B", "actor_a"),
      makeEntry("entity_attack", "A attacks again", "actor_a"),
      makeEntry("entity_attack", "B attacks A", "actor_b"),
      makeEntry("entity_attack", "B attacks again", "actor_b"),
      makeEntry("entity_attack", "A strikes back", "actor_a"),
    ]

    const result = processLogEntries(entries)

    // combat_started (event) + turn_header(A) + 2 attacks + turn_header(B) + 2 attacks + turn_header(A) + 1 attack
    const headers = result.filter((e) => e.kind === "turn_header")
    expect(headers).toHaveLength(3)

    expect(headers[0].kind === "turn_header" && headers[0].actorId).toBe("actor_a")
    expect(headers[1].kind === "turn_header" && headers[1].actorId).toBe("actor_b")
    expect(headers[2].kind === "turn_header" && headers[2].actorId).toBe("actor_a")
  })

  it("does NOT insert turn header for events with null actor_id during combat", () => {
    const entries = [
      makeEntry("combat_started", "Combat!", null),
      makeEntry("entity_attack", "A attacks", "actor_a"),
      makeEntry("weather_changed", "It starts raining", null),
      makeEntry("entity_attack", "A attacks again", "actor_a"),
    ]

    const result = processLogEntries(entries)

    const headers = result.filter((e) => e.kind === "turn_header")
    // Only one header for actor_a's initial appearance; weather doesn't reset the actor tracking
    expect(headers).toHaveLength(1)
  })

  it("does NOT insert turn headers outside of combat", () => {
    const entries = [
      makeEntry("entity_say", "Hello", "actor_a"),
      makeEntry("entity_say", "Hi there", "actor_b"),
      makeEntry("entity_say", "Goodbye", "actor_a"),
    ]

    const result = processLogEntries(entries)

    const headers = result.filter((e) => e.kind === "turn_header")
    expect(headers).toHaveLength(0)
  })

  it("stops inserting turn headers after combat_ended", () => {
    const entries = [
      makeEntry("combat_started", "Combat!", null),
      makeEntry("entity_attack", "A attacks", "actor_a"),
      makeEntry("entity_attack", "B attacks", "actor_b"),
      makeEntry("combat_ended", "Combat ended", null),
      makeEntry("entity_say", "Hello", "actor_a"),
      makeEntry("entity_say", "Hi", "actor_b"),
    ]

    const result = processLogEntries(entries)

    const headers = result.filter((e) => e.kind === "turn_header")
    // Only 2 headers during combat (A and B), none after combat_ended
    expect(headers).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// processLogEntries — basic event passthrough
// ---------------------------------------------------------------------------

describe("processLogEntries — basic", () => {
  it("wraps regular events with icon and color", () => {
    const entries = [
      makeEntry("entity_attack", "You attack the goblin", "player_1"),
    ]

    const result = processLogEntries(entries)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe("event")
    if (result[0].kind === "event") {
      expect(result[0].icon).toBe("swords")
      expect(result[0].colorClass).toContain("text-red")
      expect(result[0].entry).toBe(entries[0])
    }
  })

  it("returns empty array for empty input", () => {
    expect(processLogEntries([])).toEqual([])
  })
})
