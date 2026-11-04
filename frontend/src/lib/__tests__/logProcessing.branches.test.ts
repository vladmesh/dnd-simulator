import { describe, it, expect } from "vitest"
import { hasAttackBreakdown, processLogEntries } from "../logProcessing"
import type { AttackRollData, PerceivedEvent } from "@/types/game"
import type { LogEntry } from "@/store/slices/logSlice"

function makeEntries(events: PerceivedEvent[]): LogEntry[] {
  return events.map((event, index) => ({ id: index + 1, event }))
}

// This module is a pure transformation: no API, UI, or i18n dependencies to mock.
describe("hasAttackBreakdown — validation branches", () => {
  it("rejects absent, non-object, and incomplete attack rolls", () => {
    expect(hasAttackBreakdown(undefined)).toBe(false)
    expect(hasAttackBreakdown({})).toBe(false)

    const invalidRolls: unknown[] = [
      null,
      12,
      "attack",
      [],
      {},
      { natural: "12", total: 15, d20: { sides: 20, result: 12 } },
      { natural: 12, total: "15", d20: { sides: 20, result: 12 } },
      { natural: 12, total: 15 },
      { natural: 12, total: 15, d20: null },
    ]

    for (const attack_roll of invalidRolls) {
      expect(hasAttackBreakdown({ attack_roll })).toBe(false)
    }
  })

  it("recognizes complete attack rolls, including zero-valued numeric fields", () => {
    const roll: AttackRollData = {
      natural: 12,
      total: 15,
      d20: { sides: 20, result: 12 },
      components: [{ source: "Strength", value: 3, dice: "" }],
      advantage: false,
      disadvantage: false,
    }

    expect(hasAttackBreakdown({ attack_roll: roll })).toBe(true)
    expect(hasAttackBreakdown({
      attack_roll: { ...roll, natural: 0, total: 0 },
    })).toBe(true)
  })
})

describe("processLogEntries — uncovered branches", () => {
  it("normalizes legacy, missing, and non-numeric movement distances without overriding distance_ft", () => {
    const distances: Array<Record<string, unknown> | undefined> = [
      { distance_ft: 5, ft: 100 },
      { ft: 10 },
      { distance_ft: null, ft: 15 },
      undefined,
      {},
      { distance_ft: "20", ft: 100 },
      { ft: "25" },
      { distance_ft: 0, ft: 100 },
    ]
    const entries = makeEntries(distances.map((data) => ({
      event_type: "entity_move",
      description: "Ada moves",
      actor_id: "actor_a",
      actor_name: "Ada",
      data,
    })))

    expect(processLogEntries(entries)).toMatchObject([{
      kind: "aggregated_move",
      actorId: "actor_a",
      actorName: "Ada",
      totalDistanceFt: 30,
      entries,
    }])
  })

  it("groups omitted and null actor IDs together and uses anonymous display fallbacks", () => {
    const entries = makeEntries([
      { event_type: "entity_move", description: "Unknown movement", data: { ft: 5 } },
      { event_type: "entity_move", description: "More movement", actor_id: null, data: { ft: 10 } },
    ])

    expect(processLogEntries(entries)).toMatchObject([{
      kind: "aggregated_move",
      actorId: "?",
      actorName: "?",
      totalDistanceFt: 15,
      entries,
    }])
  })

  it("defaults round numbers to zero when the payload or round_number is absent", () => {
    const entries = makeEntries([
      { event_type: "round_start", description: "Round without data" },
      { event_type: "round_start", description: "Round without number", data: {} },
    ])

    expect(processLogEntries(entries)).toEqual([
      { kind: "round_header", roundNumber: 0 },
      { kind: "round_header", roundNumber: 0 },
    ])
  })

  it("flushes pending moves before a round header and starts a new turn for the same named mover", () => {
    const move: PerceivedEvent = {
      event_type: "entity_move",
      description: "Ada moves",
      actor_id: "actor_a",
      actor_name: "Ada",
      data: { distance_ft: 5 },
    }
    const entries = makeEntries([
      { event_type: "combat_started", description: "Combat!" },
      move,
      move,
      { event_type: "round_start", description: "Round two", data: { round_number: 2 } },
      move,
    ])
    const turnHeader = { kind: "turn_header", actorId: "actor_a", actorName: "Ada" }

    expect(processLogEntries(entries)).toMatchObject([
      { kind: "event", entry: entries[0] },
      turnHeader,
      { kind: "aggregated_move", totalDistanceFt: 10, entries: entries.slice(1, 3) },
      { kind: "round_header", roundNumber: 2 },
      turnHeader,
      { kind: "event", entry: entries[4] },
    ])
  })

  it("adds movement turn headers only for changed, identified actors during combat", () => {
    const entries = makeEntries([
      { event_type: "combat_started", description: "Combat!" },
      { event_type: "entity_attack", description: "A attacks", actor_id: "actor_a" },
      { event_type: "entity_move", description: "A moves", actor_id: "actor_a" },
      { event_type: "entity_move", description: "B moves", actor_id: "actor_b" },
      { event_type: "entity_move", description: "B moves again", actor_id: "actor_b" },
      { event_type: "entity_move", description: "Unknown movement" },
      { event_type: "entity_move", description: "More unknown movement", actor_id: null },
      { event_type: "entity_move", description: "B resumes moving", actor_id: "actor_b" },
    ])

    expect(processLogEntries(entries)).toMatchObject([
      { kind: "event", entry: entries[0] },
      { kind: "turn_header", actorId: "actor_a", actorName: "actor_a" },
      { kind: "event", entry: entries[1] },
      { kind: "event", entry: entries[2] },
      { kind: "turn_header", actorId: "actor_b", actorName: "actor_b" },
      { kind: "aggregated_move", actorId: "actor_b", entries: entries.slice(3, 5) },
      { kind: "aggregated_move", actorId: "?", entries: entries.slice(5, 7) },
      { kind: "event", entry: entries[7] },
    ])
  })

  it("resets turn tracking on a new combat and prefers actor names for non-move headers", () => {
    const entries = makeEntries([
      { event_type: "combat_started", description: "First combat" },
      { event_type: "entity_attack", description: "Ada attacks", actor_id: "actor_a", actor_name: "Ada" },
      { event_type: "combat_started", description: "New combat" },
      { event_type: "entity_attack", description: "A attacks again", actor_id: "actor_a" },
    ])

    expect(processLogEntries(entries)).toMatchObject([
      { kind: "event", entry: entries[0] },
      { kind: "turn_header", actorId: "actor_a", actorName: "Ada" },
      { kind: "event", entry: entries[1] },
      { kind: "event", entry: entries[2] },
      { kind: "turn_header", actorId: "actor_a", actorName: "actor_a" },
      { kind: "event", entry: entries[3] },
    ])
  })
})
