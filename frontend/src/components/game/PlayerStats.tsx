import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { ChevronDown, ChevronRight, Shield, Coins, ArrowUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { InventoryPanel } from "./InventoryPanel"
import { LevelUpModal } from "./LevelUpModal"

export function PlayerStats() {
  const { t } = useTranslation(["game", "common"])
  const player = useGameStore((s) => s.player)
  const sessionId = useGameStore((s) => s.sessionId)
  const updatePlayer = useGameStore((s) => s.updatePlayer)
  const levelUpDismissed = useGameStore((s) => s.levelUpDismissed)
  const setLevelUpDismissed = useGameStore((s) => s.setLevelUpDismissed)
  const [expanded, setExpanded] = useState(true)

  const levelUpAvailable = player?.level_up_available ?? false
  const levelUpOpen = levelUpAvailable && !levelUpDismissed

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
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm">
              {t(`game:race_${player.race}`, { defaultValue: player.race })}{" "}
              {t(`game:class_${player.char_class}`, { defaultValue: player.char_class })}{" "}
              L{player.level}
            </div>
            {levelUpAvailable && (
              <Button
                size="sm"
                variant="default"
                className="h-6 gap-1 px-2 text-xs"
                onClick={() => setLevelUpDismissed(false)}
              >
                <ArrowUp className="size-3" />
                {t("game:levelup_button")}
              </Button>
            )}
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
      <div className="border-t border-border" />
      <InventoryPanel />
      <LevelUpModal
        open={levelUpOpen}
        player={player}
        sessionId={sessionId ?? undefined}
        onClose={() => setLevelUpDismissed(true)}
        onSuccess={(updated) => {
          updatePlayer(updated)
          setLevelUpDismissed(false)
        }}
      />
    </div>
  )
}
