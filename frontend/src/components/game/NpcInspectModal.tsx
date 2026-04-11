import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import type { NearbyEntity, CombatEntity, MerchantInfo } from "@/types/game"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { MerchantView } from "./TradePanel"
import { Sword, MessageCircle, ShoppingBag, Send } from "lucide-react"
import { SmiteChoice, getSpellSlots } from "./SmiteChoice"

interface NpcInspectModalProps {
  entity: NearbyEntity | CombatEntity | null
  open: boolean
  onClose: () => void
  isCombat: boolean
}

function isNearbyEntity(e: NearbyEntity | CombatEntity): e is NearbyEntity {
  return "npc_description" in e
}

function sendAction(name: string, params?: Record<string, unknown>) {
  wsClient.send({ type: "action", name, params })
  useGameStore.getState().setWaitingForAction(true)
}

export function NpcInspectModal({ entity, open, onClose, isCombat }: NpcInspectModalProps) {
  const { t } = useTranslation(["game", "common"])
  const awareness = useGameStore((s) => s.awareness)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const [showTrade, setShowTrade] = useState(false)
  const [talkText, setTalkText] = useState("")
  const [showSmite, setShowSmite] = useState(false)

  if (!entity) return null

  const nearby = isNearbyEntity(entity) ? entity : null
  const combat = !isNearbyEntity(entity) ? entity : null

  // Find merchant data if this is a merchant NPC
  let merchant: MerchantInfo | undefined
  if (nearby?.is_merchant && awareness && "merchants" in awareness) {
    merchant = awareness.merchants?.find((m) => m.id === entity.id)
  }

  const displayName = nearby?.name || entity.description || entity.id
  const raceKey = nearby?.race ? `game:race_${nearby.race.toLowerCase()}` : ""
  const roleKey = nearby?.role ? `game:role_${nearby.role.toLowerCase()}` : ""

  const spellSlots = isCombat && awareness && "self_resource_pools" in awareness
    ? getSpellSlots(awareness.self_resource_pools ?? [])
    : []

  const handleAttack = () => {
    if (spellSlots.length > 0) {
      setShowSmite(true)
      return
    }
    sendAction("attack", { target_id: entity.id })
    onClose()
  }

  const handleTalk = () => {
    if (talkText.trim()) {
      sendAction("say", { target_id: entity.id, text: talkText.trim() })
      setTalkText("")
      onClose()
    }
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setShowTrade(false)
      setShowSmite(false)
      setTalkText("")
      onClose()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-sm">
            {displayName}
          </DialogTitle>
          {(raceKey || roleKey) && (
            <DialogDescription className="text-xs">
              {[
                raceKey ? t(raceKey, { defaultValue: nearby?.race }) : "",
                roleKey ? t(roleKey, { defaultValue: nearby?.role }) : "",
              ]
                .filter(Boolean)
                .join(" \u00b7 ")}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className="space-y-2 text-xs">
          {/* NPC description (peaceful only) */}
          {nearby?.npc_description && (
            <p className="text-muted-foreground">{nearby.npc_description}</p>
          )}

          {/* Faction */}
          {nearby?.faction_id && (
            <p className="text-muted-foreground">
              {t("game:faction")}: {nearby.faction_name || nearby.faction_id}
            </p>
          )}

          {/* Combat info: conditions, distance */}
          {combat && (
            <>
              {combat.conditions && combat.conditions.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {combat.conditions.map((c) => (
                    <span
                      key={c}
                      className="rounded bg-orange-500/20 px-1.5 py-0.5 text-[10px] font-medium text-orange-400"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              )}
              {combat.distance_ft != null && (
                <p className="text-muted-foreground">
                  {t("game:distance", { ft: combat.distance_ft, dir: combat.direction ?? "" })}
                </p>
              )}
            </>
          )}

          {/* Wounded indicator */}
          {entity.is_wounded && (
            <p className="font-medium text-red-400">{t("game:wounded")}</p>
          )}

          {/* Trade panel (embedded) */}
          {showTrade && merchant && (
            <div className="rounded border border-border p-2">
              <MerchantView merchant={merchant} />
            </div>
          )}

          {/* Action buttons */}
          {isMyTurn && (
            <div className="flex flex-wrap gap-1 pt-1">
              <Button size="xs" variant="destructive" onClick={handleAttack}>
                <Sword className="mr-1 size-3" /> {t("game:attack")}
              </Button>
              {!isCombat && (
                <Button
                  size="xs"
                  variant="secondary"
                  onClick={() => setTalkText((prev) => (prev === "" ? " " : ""))}
                >
                  <MessageCircle className="mr-1 size-3" /> {t("game:talk")}
                </Button>
              )}
              {!isCombat && merchant && (
                <Button
                  size="xs"
                  variant="secondary"
                  onClick={() => setShowTrade(!showTrade)}
                >
                  <ShoppingBag className="mr-1 size-3" /> {t("game:trade")}
                </Button>
              )}
            </div>
          )}

          {/* Smite choice */}
          {showSmite && (
            <SmiteChoice
              slots={spellSlots}
              onChoice={(slotLevel) => {
                const params: Record<string, unknown> = { target_id: entity.id }
                if (slotLevel != null) params.smite_slot_level = slotLevel
                sendAction("attack", params)
                setShowSmite(false)
                onClose()
              }}
              onCancel={() => setShowSmite(false)}
            />
          )}

          {/* Talk input */}
          {isMyTurn && talkText !== "" && (
            <div className="flex gap-1">
              <input
                className="h-6 flex-1 rounded border border-border bg-transparent px-1.5 text-xs placeholder:text-muted-foreground"
                placeholder={t("game:say_placeholder")}
                value={talkText.trim() === "" ? "" : talkText}
                autoFocus
                onChange={(e) => setTalkText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTalk()
                  if (e.key === "Escape") setTalkText("")
                }}
              />
              <Button size="xs" variant="secondary" disabled={!talkText.trim()} onClick={handleTalk}>
                <Send className="size-3" />
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
