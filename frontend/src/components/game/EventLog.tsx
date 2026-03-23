import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import { useVirtualizer } from "@tanstack/react-virtual"
import { useGameStore } from "@/store/gameStore"

const EVENT_COLORS: Record<string, string> = {
  entity_attack: "text-red-400",
  entity_died: "text-red-500 font-bold",
  combat_started: "text-orange-400",
  combat_ended: "text-green-400",
  entity_say: "text-blue-400",
  entity_move: "text-muted-foreground",
  entity_dodge: "text-yellow-400",
  entity_flee: "text-yellow-400",
  action_error: "text-red-300 italic",
  weather_changed: "text-sky-400",
  time_advanced: "text-muted-foreground",
}

export function EventLog() {
  const { t } = useTranslation(["common"])
  const log = useGameStore((s) => s.log)
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
    // virtualizer is stable, only scroll when log grows
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logLength])

  return (
    <div ref={parentRef} className="flex-1 overflow-y-auto font-mono text-xs">
      {log.length === 0 ? (
        <div className="flex h-full items-center justify-center text-muted-foreground">
          {t("common:waiting_for_events")}
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
                <span className="text-muted-foreground/60">[{entry.event.event_type}]</span>{" "}
                <span className={colorClass}>{entry.event.description}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
