import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import type { CombatAwareness } from "@/types/game"

export function BattleMap() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)

  if (!awareness || !("self_hp" in awareness)) return null
  const combat = awareness as CombatAwareness
  if (!combat.battle_map_ascii) return null

  return (
    <div className="space-y-1">
      <h3 className="text-xs font-medium uppercase text-muted-foreground">
        {t("game:battle_map")}
      </h3>
      <pre className="overflow-auto rounded border border-border bg-muted/50 p-2 font-mono text-xs leading-tight">
        {combat.battle_map_ascii}
      </pre>
    </div>
  )
}
