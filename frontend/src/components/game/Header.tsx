import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import type { PeacefulAwareness } from "@/types/game"

function hpColor(hp: number, max: number): string {
  const pct = max > 0 ? hp / max : 0
  if (pct > 0.5) return "bg-green-500"
  if (pct > 0.25) return "bg-yellow-500"
  return "bg-red-500"
}

function formatTime(a: PeacefulAwareness): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `Y${a.year} M${a.month} D${a.day} ${pad(a.hour)}:00`
}

function weatherLabel(weather: Record<string, unknown>): string {
  const desc = weather.description ?? weather.condition ?? weather.type
  return typeof desc === "string" ? desc : ""
}

export function Header() {
  const { t } = useTranslation(["game"])
  const player = useGameStore((s) => s.player)
  const awareness = useGameStore((s) => s.awareness)
  const location = useGameStore((s) => s.location)
  const wsStatus = useGameStore((s) => s.wsStatus)

  if (!player) return null

  const pct = player.max_hp > 0 ? Math.round((player.hp / player.max_hp) * 100) : 0
  const peaceful = awareness && "hour" in awareness ? (awareness as PeacefulAwareness) : null

  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border px-4 py-2 text-sm">
      {/* HP bar */}
      <div className="flex items-center gap-2">
        <span className="font-medium">{player.name}</span>
        <div className="relative h-4 w-32 overflow-hidden rounded-full bg-muted">
          <div
            className={`absolute inset-y-0 left-0 transition-all ${hpColor(player.hp, player.max_hp)}`}
            style={{ width: `${pct}%` }}
          />
          <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-foreground">
            {t("game:header_hp", { hp: player.hp, max: player.max_hp })}
          </span>
        </div>
      </div>

      {/* Location */}
      {location && (
        <span className="text-muted-foreground">
          {location.current_location}
        </span>
      )}

      {/* Time & Weather */}
      {peaceful && (
        <>
          <span className="text-muted-foreground">{formatTime(peaceful)}</span>
          {peaceful.weather && weatherLabel(peaceful.weather) && (
            <span className="text-muted-foreground">{weatherLabel(peaceful.weather)}</span>
          )}
        </>
      )}

      {/* WS status indicator */}
      <span className="ml-auto">
        <span
          className={`inline-block size-2 rounded-full ${
            wsStatus === "connected" ? "bg-green-500" : wsStatus === "connecting" ? "bg-yellow-500" : "bg-red-500"
          }`}
        />
      </span>
    </header>
  )
}
