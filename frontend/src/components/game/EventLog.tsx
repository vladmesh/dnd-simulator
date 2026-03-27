import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useVirtualizer } from "@tanstack/react-virtual"
import {
  ChevronDown,
  ChevronRight,
  Swords,
  Skull,
  MessageCircle,
  Footprints,
  Zap,
  Shield,
  Rabbit,
  ArrowLeftRight,
  Sparkles,
  FlaskRound,
  HeartPulse,
  Sword,
  PackageOpen,
  Coins,
  HandCoins,
  TriangleAlert,
  Clock,
  Flame,
  Flag,
  Users,
  CloudSun,
  Hourglass,
  MapPin,
  ShieldAlert,
  Eye,
  EyeOff,
  Scroll,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useGameStore } from "@/store/gameStore"
import {
  processLogEntries,
  EVENT_COLORS,
} from "@/lib/logProcessing"
import type { DisplayEntry } from "@/lib/logProcessing"

// ---------------------------------------------------------------------------
// Icon name → component mapping
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, LucideIcon> = {
  swords: Swords,
  skull: Skull,
  "message-circle": MessageCircle,
  footprints: Footprints,
  zap: Zap,
  shield: Shield,
  rabbit: Rabbit,
  "arrow-left-right": ArrowLeftRight,
  sparkles: Sparkles,
  "flask-round": FlaskRound,
  "heart-pulse": HeartPulse,
  sword: Sword,
  "package-open": PackageOpen,
  coins: Coins,
  "hand-coins": HandCoins,
  "alert-triangle": TriangleAlert,
  clock: Clock,
  flame: Flame,
  flag: Flag,
  users: Users,
  "cloud-sun": CloudSun,
  hourglass: Hourglass,
  "map-pin": MapPin,
  "shield-alert": ShieldAlert,
  eye: Eye,
  "eye-off": EyeOff,
  scroll: Scroll,
}

function EventIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICON_MAP[name]
  if (!Icon) return null
  return <Icon className={className ?? "size-3 shrink-0"} />
}

// ---------------------------------------------------------------------------
// Compact visible count
// ---------------------------------------------------------------------------

const COMPACT_VISIBLE_COUNT = 5

// ---------------------------------------------------------------------------
// EventLog — public component
// ---------------------------------------------------------------------------

interface EventLogProps {
  compact?: boolean
  onExpand?: () => void
}

export function EventLog({ compact, onExpand }: EventLogProps) {
  const { t } = useTranslation(["common"])
  const log = useGameStore((s) => s.log)
  const displayEntries = useMemo(() => processLogEntries(log), [log])

  if (compact) {
    return <CompactLog displayEntries={displayEntries} onExpand={onExpand} />
  }

  return <FullLog displayEntries={displayEntries} emptyMessage={t("common:waiting_for_events")} />
}

// ---------------------------------------------------------------------------
// Shared entry renderer
// ---------------------------------------------------------------------------

function DisplayEntryRow({
  entry,
  expanded,
  onToggleExpand,
}: {
  entry: DisplayEntry
  expanded?: boolean
  onToggleExpand?: () => void
}) {
  if (entry.kind === "turn_header") {
    return (
      <div
        data-testid="turn-header"
        className="flex items-center gap-2 border-t border-border/50 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        <div className="h-px flex-1 bg-border/50" />
        <span>{entry.actorName}</span>
        <div className="h-px flex-1 bg-border/50" />
      </div>
    )
  }

  if (entry.kind === "aggregated_move") {
    return (
      <div className="px-3 py-0.5">
        <div className="flex items-center gap-1.5">
          <button
            data-testid="aggregated-move-expand"
            onClick={onToggleExpand}
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
          </button>
          <EventIcon name={entry.icon} className="size-3 shrink-0 text-muted-foreground" />
          <span className={entry.colorClass}>
            {entry.actorName} moved ({entry.totalDistanceFt} ft)
          </span>
        </div>
        {expanded && (
          <div className="ml-6 mt-0.5 space-y-0.5 border-l border-border/30 pl-2">
            {entry.entries.map((sub) => {
              const subColor = EVENT_COLORS[sub.event.event_type]
              return (
                <div key={sub.id} className="flex items-center gap-1.5">
                  <EventIcon
                    name="footprints"
                    className="size-2.5 shrink-0 text-muted-foreground/60"
                  />
                  <span className={`text-[10px] ${subColor}`}>{sub.event.description}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  // kind === "event"
  return (
    <div className="flex items-center gap-1.5 px-3 py-0.5">
      <EventIcon name={entry.icon} className={`size-3 shrink-0 ${entry.colorClass}`} />
      <span className={entry.colorClass}>{entry.entry.event.description}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CompactLog
// ---------------------------------------------------------------------------

function CompactLog({
  displayEntries,
  onExpand,
}: {
  displayEntries: DisplayEntry[]
  onExpand?: () => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [expandedMoves, setExpandedMoves] = useState<Set<number>>(new Set())

  // Auto-scroll to bottom
  const entryCount = displayEntries.length
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [entryCount])

  const visible = displayEntries.slice(-COMPACT_VISIBLE_COUNT)

  return (
    <div className="flex items-stretch border-b border-border">
      <div
        ref={scrollRef}
        className="max-h-24 flex-1 overflow-y-auto font-mono text-xs"
        data-testid="compact-log"
      >
        {visible.map((entry, idx) => (
          <DisplayEntryRow
            key={entry.kind === "event" ? entry.entry.id : `${entry.kind}-${idx}`}
            entry={entry}
            expanded={entry.kind === "aggregated_move" && expandedMoves.has(idx)}
            onToggleExpand={() => {
              setExpandedMoves((prev) => {
                const next = new Set(prev)
                if (next.has(idx)) next.delete(idx)
                else next.add(idx)
                return next
              })
            }}
          />
        ))}
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

// ---------------------------------------------------------------------------
// FullLog (virtualized)
// ---------------------------------------------------------------------------

function FullLog({
  displayEntries,
  emptyMessage,
}: {
  displayEntries: DisplayEntry[]
  emptyMessage: string
}) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [expandedMoves, setExpandedMoves] = useState<Set<number>>(new Set())

  const virtualizer = useVirtualizer({
    count: displayEntries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => {
      const entry = displayEntries[index]
      if (entry.kind === "turn_header") return 28
      if (entry.kind === "aggregated_move" && expandedMoves.has(index)) {
        return 24 + entry.entries.length * 20
      }
      return 24
    },
    overscan: 10,
  })

  // Auto-scroll to bottom on new events
  const entryCount = displayEntries.length
  useEffect(() => {
    if (entryCount > 0) {
      virtualizer.scrollToIndex(entryCount - 1, { align: "end" })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entryCount])

  return (
    <div ref={parentRef} className="flex-1 overflow-y-auto font-mono text-xs">
      {displayEntries.length === 0 ? (
        <div className="flex h-full items-center justify-center text-muted-foreground">
          {emptyMessage}
        </div>
      ) : (
        <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
          {virtualizer.getVirtualItems().map((vRow) => {
            const entry = displayEntries[vRow.index]
            return (
              <div
                key={vRow.index}
                className="absolute left-0 top-0 w-full"
                style={{
                  height: `${vRow.size}px`,
                  transform: `translateY(${vRow.start}px)`,
                }}
              >
                <DisplayEntryRow
                  entry={entry}
                  expanded={entry.kind === "aggregated_move" && expandedMoves.has(vRow.index)}
                  onToggleExpand={() => {
                    setExpandedMoves((prev) => {
                      const next = new Set(prev)
                      if (next.has(vRow.index)) next.delete(vRow.index)
                      else next.add(vRow.index)
                      return next
                    })
                  }}
                />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
