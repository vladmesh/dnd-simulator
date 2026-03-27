import type { EventType, PerceivedEvent } from "@/types/game"
import type { LogEntry } from "@/store/slices/logSlice"

// ---------------------------------------------------------------------------
// Display entry types
// ---------------------------------------------------------------------------

export interface EventDisplayEntry {
  kind: "event"
  entry: LogEntry
  icon: string
  colorClass: string
}

export interface TurnHeaderEntry {
  kind: "turn_header"
  actorId: string
  actorName: string
}

export interface AggregatedMoveEntry {
  kind: "aggregated_move"
  actorId: string
  actorName: string
  totalDistanceFt: number
  entries: LogEntry[]
  icon: string
  colorClass: string
}

export type DisplayEntry = EventDisplayEntry | TurnHeaderEntry | AggregatedMoveEntry

// ---------------------------------------------------------------------------
// Icon and color mappings
// ---------------------------------------------------------------------------

export const EVENT_ICONS: Record<EventType, string> = {
  entity_attack: "swords",
  entity_died: "skull",
  entity_say: "message-circle",
  entity_move: "footprints",
  entity_dash: "zap",
  entity_dodge: "shield",
  entity_flee: "rabbit",
  entity_disengage: "arrow-left-right",
  entity_bless: "sparkles",
  entity_use_item: "flask-round",
  entity_second_wind: "heart-pulse",
  entity_equip: "sword",
  entity_unequip: "package-open",
  entity_buy: "coins",
  entity_sell: "hand-coins",
  action_error: "alert-triangle",
  turn_skipped: "clock",
  combat_started: "flame",
  combat_ended: "flag",
  encounter_spawned: "users",
  weather_changed: "cloud-sun",
  time_advanced: "hourglass",
  squad_move: "map-pin",
  squad_combat: "shield-alert",
  squad_materialized: "eye",
  squad_dematerialized: "eye-off",
  custom: "scroll",
}

export const EVENT_COLORS: Record<EventType, string> = {
  entity_attack: "text-red-400",
  entity_died: "text-red-500 font-bold",
  entity_say: "text-blue-400",
  entity_move: "text-muted-foreground",
  entity_dash: "text-muted-foreground",
  entity_dodge: "text-yellow-400",
  entity_flee: "text-yellow-400",
  entity_disengage: "text-yellow-400",
  entity_bless: "text-emerald-400",
  entity_use_item: "text-purple-400",
  entity_second_wind: "text-green-400",
  entity_equip: "text-foreground",
  entity_unequip: "text-foreground",
  entity_buy: "text-amber-400",
  entity_sell: "text-amber-400",
  action_error: "text-red-300 italic",
  turn_skipped: "text-muted-foreground italic",
  combat_started: "text-orange-400",
  combat_ended: "text-green-400",
  encounter_spawned: "text-orange-400",
  weather_changed: "text-sky-400",
  time_advanced: "text-muted-foreground",
  squad_move: "text-muted-foreground",
  squad_combat: "text-orange-400",
  squad_materialized: "text-yellow-400",
  squad_dematerialized: "text-muted-foreground",
  custom: "text-foreground",
}

// ---------------------------------------------------------------------------
// Processing
// ---------------------------------------------------------------------------

function isMoveLike(eventType: EventType): boolean {
  return eventType === "entity_move" || eventType === "entity_dash"
}

function getDistanceFt(event: PerceivedEvent): number {
  const d = event.data?.distance_ft ?? event.data?.ft
  return typeof d === "number" ? d : 0
}

function actorNameFromEntry(entry: LogEntry): string {
  return entry.event.actor_id ?? "?"
}

function makeEventDisplay(entry: LogEntry): EventDisplayEntry {
  return {
    kind: "event",
    entry,
    icon: EVENT_ICONS[entry.event.event_type],
    colorClass: EVENT_COLORS[entry.event.event_type],
  }
}

function flushMoveBuffer(buffer: LogEntry[]): DisplayEntry {
  if (buffer.length === 1) {
    return makeEventDisplay(buffer[0])
  }
  const totalDist = buffer.reduce((sum, e) => sum + getDistanceFt(e.event), 0)
  const actorId = buffer[0].event.actor_id ?? "?"
  return {
    kind: "aggregated_move",
    actorId,
    actorName: actorNameFromEntry(buffer[0]),
    totalDistanceFt: totalDist,
    entries: [...buffer],
    icon: EVENT_ICONS["entity_move"],
    colorClass: EVENT_COLORS["entity_move"],
  }
}

export function processLogEntries(entries: LogEntry[]): DisplayEntry[] {
  if (entries.length === 0) return []

  const result: DisplayEntry[] = []
  let inCombat = false
  let lastCombatActorId: string | null = null
  let moveBuffer: LogEntry[] = []

  function flush() {
    if (moveBuffer.length > 0) {
      result.push(flushMoveBuffer(moveBuffer))
      moveBuffer = []
    }
  }

  for (const entry of entries) {
    const { event } = entry
    const eventType = event.event_type

    // Track combat state
    if (eventType === "combat_started") {
      inCombat = true
      lastCombatActorId = null
    } else if (eventType === "combat_ended") {
      inCombat = false
      lastCombatActorId = null
    }

    // Move aggregation: accumulate consecutive move/dash from same actor
    if (isMoveLike(eventType)) {
      const currentActorId = event.actor_id ?? null
      if (
        moveBuffer.length > 0 &&
        (moveBuffer[0].event.actor_id ?? null) === currentActorId
      ) {
        moveBuffer.push(entry)
        continue
      }
      // Different actor or fresh buffer
      flush()
      moveBuffer = [entry]
      // Still need to handle turn header for this actor below — but since
      // we continue, we must emit the turn header before buffering.
      // Actually, let's emit turn header before the move buffer starts.
      if (inCombat && currentActorId != null && currentActorId !== lastCombatActorId) {
        lastCombatActorId = currentActorId
        result.push({
          kind: "turn_header",
          actorId: currentActorId,
          actorName: currentActorId,
        })
      }
      continue
    }

    // Non-move event — flush any pending moves first
    flush()

    // Turn headers (combat only, non-null actor_id)
    if (
      inCombat &&
      event.actor_id != null &&
      event.actor_id !== lastCombatActorId
    ) {
      lastCombatActorId = event.actor_id
      result.push({
        kind: "turn_header",
        actorId: event.actor_id,
        actorName: event.actor_id,
      })
    }

    result.push(makeEventDisplay(entry))
  }

  // Flush any remaining moves
  flush()

  return result
}
