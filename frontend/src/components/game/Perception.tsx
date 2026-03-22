import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { CombatAwareness } from "@/types/game"
import { Button } from "@/components/ui/button"
import { Eye, Sword, MessageCircle } from "lucide-react"

export function Perception() {
  const { t } = useTranslation(["game", "common"])
  const awareness = useGameStore((s) => s.awareness)
  const mode = useGameStore((s) => s.mode)
  const isMyTurn = useGameStore((s) => s.isMyTurn)

  if (!awareness) return null

  const nearby = awareness.nearby
  const isCombat = mode === "combat" && "self_hp" in awareness

  const sendAction = (name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
  }

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium uppercase text-muted-foreground">
        {isCombat ? t("game:enemies") : t("game:nearby")}
      </h3>
      {nearby.length === 0 && (
        <p className="text-xs text-muted-foreground">{t("common:nobody_around")}</p>
      )}
      {nearby.map((entity) => {
        const combat = isCombat ? (entity as CombatAwareness["nearby"][0]) : null
        return (
          <div key={entity.id} className="rounded border border-border p-2 text-xs">
            <div className="flex items-start justify-between gap-1">
              <div>
                <span className="font-medium">{entity.id}</span>
                {entity.is_wounded && <span className="ml-1 text-red-400">{t("game:wounded")}</span>}
              </div>
            </div>
            <p className="mt-0.5 text-muted-foreground">{entity.description}</p>
            {combat && combat.distance_ft != null && (
              <p className="text-muted-foreground">
                {t("game:distance", { ft: combat.distance_ft, dir: combat.direction ?? "" })}
              </p>
            )}
            {isMyTurn && (
              <div className="mt-1 flex gap-1">
                {isCombat ? (
                  <Button
                    size="xs"
                    variant="destructive"
                    onClick={() => sendAction("attack", { target_id: entity.id })}
                  >
                    <Sword className="mr-1 size-3" /> {t("game:attack")}
                  </Button>
                ) : (
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => sendAction("say", { target_id: entity.id })}
                  >
                    <MessageCircle className="mr-1 size-3" /> {t("game:talk")}
                  </Button>
                )}
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => wsClient.send({ type: "command", text: `look ${entity.id}` })}
                >
                  <Eye className="size-3" />
                </Button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
