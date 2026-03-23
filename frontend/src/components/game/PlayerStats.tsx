import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { ChevronDown, ChevronRight, Shield, Coins } from "lucide-react"

export function PlayerStats() {
  const { t } = useTranslation(["game", "common"])
  const player = useGameStore((s) => s.player)
  const [expanded, setExpanded] = useState(true)

  if (!player) return null

  return (
    <div className="space-y-2">
      <button
        className="flex w-full items-center gap-1 text-xs font-medium uppercase text-muted-foreground"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        {t("game:character")}
      </button>
      {expanded && (
        <div className="space-y-2 text-xs">
          <div className="text-sm">
            {t(`game:race_${player.race}`, { defaultValue: player.race })}{" "}
            {t(`game:class_${player.char_class}`, { defaultValue: player.char_class })}{" "}
            L{player.level}
          </div>
          <div className="flex gap-3">
            <span className="flex items-center gap-1">
              <Shield className="size-3" /> AC {player.ac}
            </span>
            <span className="flex items-center gap-1">
              <Coins className="size-3" /> {player.gold}g
            </span>
          </div>
          {/* Ability scores grid */}
          <div className="grid grid-cols-3 gap-1">
            {Object.entries(player.ability_scores).map(([key, val]) => (
              <div key={key} className="rounded border border-border px-2 py-1 text-center">
                <div className="text-[10px] text-muted-foreground">{t(`common:ability_${key}`)}</div>
                <div className="font-medium">{val}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
