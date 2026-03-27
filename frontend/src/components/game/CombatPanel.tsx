import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness, CombatEntity } from "@/types/game"
import { Button } from "@/components/ui/button"
import { Sword, Eye } from "lucide-react"
import { NpcInspectModal } from "./NpcInspectModal"

export function CombatPanel() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const [inspectEntity, setInspectEntity] = useState<CombatEntity | null>(null)

  if (!awareness || !("self_hp" in awareness)) return null
  const combat = awareness as CombatAwareness

  const sendAction = (name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
  }

  const hpPct = combat.self_max_hp > 0 ? (combat.self_hp / combat.self_max_hp) * 100 : 0
  const hpColor = hpPct > 50 ? "bg-green-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"

  return (
    <div className="space-y-3">
      {/* Round indicator */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium uppercase text-muted-foreground">
          {t("game:combat_info")}
        </h3>
        <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
          {t("game:round", { n: combat.round_number })}
        </span>
      </div>

      {/* Self stats */}
      <div className="space-y-1 rounded border border-border p-2 text-xs">
        <p className="font-medium">{t("game:self_stats")}</p>
        {/* HP bar */}
        <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`absolute inset-y-0 left-0 transition-all ${hpColor}`}
            style={{ width: `${hpPct}%` }}
          />
          <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium">
            {t("game:hp_display", { hp: combat.self_hp, max: combat.self_max_hp })}
          </span>
        </div>
        <div className="flex flex-wrap gap-x-3 text-muted-foreground">
          <span>{t("game:ac_display", { n: combat.self_ac })}</span>
          <span>{t("game:speed_display", { n: combat.self_speed })}</span>
        </div>
        {combat.self_conditions && combat.self_conditions.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {combat.self_conditions.map((c) => (
              <span key={c} className="rounded bg-orange-500/20 px-1.5 py-0.5 text-[10px] font-medium text-orange-400">
                {c}
              </span>
            ))}
          </div>
        )}
        <p className="text-muted-foreground">
          {t("game:weapon_display", { name: combat.self_weapon, damage: combat.self_weapon_damage })}
        </p>
      </div>

      {/* Enemies list */}
      <div className="space-y-1.5">
        <h4 className="text-xs font-medium uppercase text-muted-foreground">
          {t("game:enemies")}
        </h4>
        {combat.nearby.length === 0 && (
          <p className="text-xs text-muted-foreground">{t("common:nobody_around")}</p>
        )}
        {combat.nearby.map((entity) => (
          <div key={entity.id} className="rounded border border-border p-2 text-xs">
            <div className="flex items-start justify-between gap-1">
              <span className="font-medium">{entity.description}</span>
              {entity.is_wounded && (
                <span className="text-red-400">{t("game:wounded")}</span>
              )}
            </div>
            <p className="mt-0.5 font-mono text-muted-foreground">{entity.id}</p>
            {entity.conditions && entity.conditions.length > 0 && (
              <div className="mt-0.5 flex flex-wrap gap-1">
                {entity.conditions.map((c) => (
                  <span key={c} className="rounded bg-orange-500/20 px-1.5 py-0.5 text-[10px] font-medium text-orange-400">
                    {c}
                  </span>
                ))}
              </div>
            )}
            {entity.distance_ft != null && (
              <p className="text-muted-foreground">
                {t("game:distance", { ft: entity.distance_ft, dir: entity.direction ?? "" })}
              </p>
            )}
            {isMyTurn && (
              <div className="mt-1 flex gap-1">
                <Button
                  size="xs"
                  variant="destructive"
                  onClick={() => sendAction("attack", { target_id: entity.id })}
                >
                  <Sword className="mr-1 size-3" /> {t("game:attack")}
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setInspectEntity(entity)}
                >
                  <Eye className="size-3" />
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>

      <NpcInspectModal
        entity={inspectEntity}
        open={inspectEntity !== null}
        onClose={() => setInspectEntity(null)}
        isCombat={true}
      />
    </div>
  )
}
