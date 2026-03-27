import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import { useVirtualizer } from "@tanstack/react-virtual"
import { ChevronDown } from "lucide-react"
import { useGameStore } from "@/store/gameStore"

export const EVENT_COLORS: Record<string, string> = {
  entity_attack: "text-red-400",
  entity_died: "text-red-500 font-bold",
  combat_started: "text-orange-400",
  combat_ended: "text-green-400",
  entity_say: "text-blue-400",
  entity_move: "text-muted-foreground",
  entity_dodge: "text-yellow-400",
  entity_flee: "text-yellow-400",
  turn_skipped: "text-muted-foreground italic",
  action_error: "text-red-300 italic",
  weather_changed: "text-sky-400",
  time_advanced: "text-muted-foreground",
  squad_move: "text-muted-foreground",
  squad_combat: "text-orange-400",
  squad_materialized: "text-yellow-400",
  squad_dematerialized: "text-muted-foreground",
}

const COMPACT_VISIBLE_COUNT = 5

interface EventLogProps {
  compact?: boolean
  onExpand?: () => void
}

export function EventLog({ compact, onExpand }: EventLogProps) {
  const { t } = useTranslation(["common"])
  const log = useGameStore((s) => s.log)

  if (compact) {
    return <CompactLog onExpand={onExpand} />
  }

  return <FullLog log={log} emptyMessage={t("common:waiting_for_events")} />
}

function CompactLog({ onExpand }: { onExpand?: () => void }) {
  const log = useGameStore((s) => s.log)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  const logLength = log.length
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [logLength])

  const visible = log.slice(-COMPACT_VISIBLE_COUNT)

  return (
    <div className="flex items-stretch border-b border-border">
      <div
        ref={scrollRef}
        className="max-h-24 flex-1 overflow-y-auto font-mono text-xs"
        data-testid="compact-log"
      >
        {visible.map((entry) => {
          const colorClass = EVENT_COLORS[entry.event.event_type] ?? "text-foreground"
          return (
            <div key={entry.id} className="px-3 py-0.5">
              <span className={colorClass}>{entry.event.description}</span>
            </div>
          )
        })}
      </div>
      {onExpand && (
        <button
          data-testid="log-expand-btn"
          className="px-2 text-muted-foreground transition-colors hover:text-foreground"
          onClick={onExpand}
        >
          <ChevronDown className="size-4" />
        </button>
      )}
    </div>
  )
}

interface FullLogProps {
  log: ReturnType<typeof useGameStore.getState>["log"]
  emptyMessage: string
}

function FullLog({ log, emptyMessage }: FullLogProps) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: log.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 24,
    overscan: 10,
  })

  // Auto-scroll to bottom on new events
  const logLength = log.length
  useEffect(() => {
    if (logLength > 0) {
      virtualizer.scrollToIndex(logLength - 1, { align: "end" })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logLength])

  return (
    <div ref={parentRef} className="flex-1 overflow-y-auto font-mono text-xs">
      {log.length === 0 ? (
        <div className="flex h-full items-center justify-center text-muted-foreground">
          {emptyMessage}
        </div>
      ) : (
        <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
          {virtualizer.getVirtualItems().map((vRow) => {
            const entry = log[vRow.index]
            const colorClass = EVENT_COLORS[entry.event.event_type] ?? "text-foreground"
            return (
              <div
                key={entry.id}
                className="absolute left-0 top-0 w-full px-3 py-0.5"
                style={{ height: `${vRow.size}px`, transform: `translateY(${vRow.start}px)` }}
              >
                <span className={colorClass}>{entry.event.description}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
