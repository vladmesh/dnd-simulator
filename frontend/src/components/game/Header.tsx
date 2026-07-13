import { useNavigate, useParams } from "react-router"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { LogOut } from "lucide-react"
import { LanguageToggle } from "@/components/setup/LanguageToggle"
import type { GameTime } from "@/store/slices/turnSlice"

function hpColor(hp: number, max: number): string {
  const pct = max > 0 ? hp / max : 0
  if (pct > 0.5) return "bg-green-500"
  if (pct > 0.25) return "bg-yellow-500"
  return "bg-red-500"
}

function formatTime(t: GameTime): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `Y${t.year} M${t.month} D${t.day} ${pad(t.hour)}:00`
}

export function Header() {
  const navigate = useNavigate()
  const { sessionId } = useParams<{ sessionId: string }>()
  const { t } = useTranslation(["game", "common"])
  const player = useGameStore((s) => s.player)
  const gameTime = useGameStore((s) => s.gameTime)
  const location = useGameStore((s) => s.location)
  const wsStatus = useGameStore((s) => s.wsStatus)

  if (!player) return null

  const pct = player.max_hp > 0 ? Math.round((player.hp / player.max_hp) * 100) : 0

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

      {/* Time */}
      {gameTime && (
        <span className="text-muted-foreground">{formatTime(gameTime)}</span>
      )}

      {/* WS status + exit */}
      <div className="ml-auto flex items-center gap-2">
        <LanguageToggle sessionId={sessionId} />
        <span
          className={`inline-block size-2 rounded-full ${
            wsStatus === "connected" ? "bg-green-500" : wsStatus === "connecting" ? "bg-yellow-500" : "bg-red-500"
          }`}
        />
        <button
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title={t("common:exit_session")}
          onClick={() => {
            useGameStore.getState().disconnect()
            navigate("/")
          }}
        >
          <LogOut className="size-4" />
        </button>
      </div>
    </header>
  )
}
