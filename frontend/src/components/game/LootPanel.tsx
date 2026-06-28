import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { ChevronDown, ChevronRight, Skull, Coins } from "lucide-react"
import type { NearbyEntity } from "@/types/game"

function sendAction(name: string, params?: Record<string, unknown>) {
  wsClient.send({ type: "action", name, params })
  useGameStore.getState().setWaitingForAction(true)
}

export function LootView({ holder }: { holder: NearbyEntity }) {
  const { t } = useTranslation(["game"])
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const items = holder.loot_items ?? []
  const gold = holder.loot_gold ?? 0
  const isEmpty = items.length === 0 && gold === 0

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="min-w-0 flex-1 truncate font-medium">{holder.name || holder.description}</span>
        <button
          className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
          disabled={waitingForAction || isEmpty}
          onClick={() => sendAction("take", { target_id: holder.id })}
        >
          {t("game:take_all")}
        </button>
      </div>

      {isEmpty ? (
        <div className="text-[10px] text-muted-foreground">{t("game:loot_empty")}</div>
      ) : (
        <div className="max-h-32 space-y-0.5 overflow-y-auto">
          {gold > 0 && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Coins className="size-3" />
              {gold}g
            </div>
          )}
          {items.map((item) => (
            <div key={item.id} className="truncate text-xs" title={item.description}>
              {item.name}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function LootPanel() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)
  const [expanded, setExpanded] = useState(true)

  // Only show in peaceful mode when lootable holders are nearby
  const nearby = (awareness && "nearby" in awareness ? awareness.nearby : undefined) ?? []
  const lootables = nearby.filter((n) => "lootable" in n && n.lootable)
  if (lootables.length === 0) return null

  return (
    <div className="space-y-2">
      <button
        className="flex w-full items-center gap-1 text-xs font-medium uppercase text-muted-foreground"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <Skull className="size-3" />
        {t("game:loot")}
      </button>
      {expanded && (
        <div className="space-y-3">
          {lootables.map((holder) => (
            <LootView key={holder.id} holder={holder as NearbyEntity} />
          ))}
        </div>
      )}
    </div>
  )
}
