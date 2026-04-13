import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { NearbyEntity } from "@/types/game"
import { Button } from "@/components/ui/button"
import { Eye, Sword, MessageCircle, Send } from "lucide-react"
import { NpcInspectModal } from "./NpcInspectModal"
import { SmiteChoice, getSpellSlots } from "./SmiteChoice"

export function Perception() {
  const { t } = useTranslation(["game", "common"])
  const awareness = useGameStore((s) => s.awareness)
  const mode = useGameStore((s) => s.mode)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const [talkTarget, setTalkTarget] = useState<string | null>(null)
  const [talkText, setTalkText] = useState("")
  const [inspectEntity, setInspectEntity] = useState<NearbyEntity | null>(null)
  const [smiteTarget, setSmiteTarget] = useState<string | null>(null)

  if (!awareness) return null

  const nearby = awareness.nearby
  const isCombat = mode === "combat" && "self_hp" in awareness
  const spellSlots = isCombat && "self_resource_pools" in awareness
    ? getSpellSlots(awareness.self_resource_pools ?? [])
    : []

  const sendAction = (name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
  }

  const submitTalk = () => {
    if (talkText.trim()) {
      sendAction("say", { target_id: talkTarget, text: talkText.trim() })
      setTalkText("")
      setTalkTarget(null)
    }
  }

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium uppercase text-muted-foreground">
        {isCombat ? t("game:enemies") : t("game:nearby")}
      </h3>
      {nearby.length === 0 && (
        <p className="text-xs text-muted-foreground">{t("common:nobody_around")}</p>
      )}
      {nearby.map((entity) => (
        <div key={entity.id} className="rounded border border-border p-2 text-xs">
          <div className="flex items-start justify-between gap-1">
            <div>
              <span className="font-medium">{entity.description || entity.id}</span>
              {entity.is_wounded && <span className="ml-1 text-red-400">{t("game:wounded")}</span>}
            </div>
          </div>
          {entity.description && entity.description !== entity.id && (
            <p className="mt-0.5 text-muted-foreground">{entity.id}</p>
          )}
          {isMyTurn && (
            <div className="mt-1 space-y-1">
              <div className="flex gap-1">
                <Button
                  size="xs"
                  variant="destructive"
                  onClick={() => {
                    if (spellSlots.length > 0) {
                      setSmiteTarget(smiteTarget === entity.id ? null : entity.id)
                    } else {
                      sendAction("attack", { target_id: entity.id })
                    }
                  }}
                >
                  <Sword className="mr-1 size-3" /> {t("game:attack")}
                </Button>
                {!isCombat && (
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => setTalkTarget(talkTarget === entity.id ? null : entity.id)}
                  >
                    <MessageCircle className="mr-1 size-3" /> {t("game:talk")}
                  </Button>
                )}
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setInspectEntity(entity)}
                >
                  <Eye className="size-3" />
                </Button>
              </div>
              {smiteTarget === entity.id && (
                <SmiteChoice
                  slots={spellSlots}
                  targetName={entity.id}
                  onChoice={(slotLevel) => {
                    const params: Record<string, unknown> = { target_id: entity.id }
                    if (slotLevel != null) params.smite_slot_level = slotLevel
                    sendAction("attack", params)
                    setSmiteTarget(null)
                  }}
                  onCancel={() => setSmiteTarget(null)}
                />
              )}
              {talkTarget === entity.id && (
                <div className="flex gap-1">
                  <input
                    className="h-6 flex-1 rounded border border-border bg-transparent px-1.5 text-xs placeholder:text-muted-foreground"
                    placeholder={t("game:say_placeholder")}
                    value={talkText}
                    autoFocus
                    onChange={(e) => setTalkText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitTalk()
                      if (e.key === "Escape") { setTalkTarget(null); setTalkText("") }
                    }}
                  />
                  <Button size="xs" variant="secondary" disabled={!talkText.trim()} onClick={submitTalk}>
                    <Send className="size-3" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      <NpcInspectModal
        entity={inspectEntity}
        open={inspectEntity !== null}
        onClose={() => setInspectEntity(null)}
        isCombat={isCombat}
      />
    </div>
  )
}
