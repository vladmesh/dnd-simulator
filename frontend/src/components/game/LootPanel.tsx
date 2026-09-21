import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { ChevronDown, ChevronRight, Skull, Coins } from "lucide-react"
import type { CombatLootable, NearbyEntity } from "@/types/game"
import { ItemDetails } from "./ItemDetails"

function sendAction(name: string, params?: Record<string, unknown>) {
  wsClient.send({ type: "action", name, params })
  useGameStore.getState().setWaitingForAction(true)
}

export function LootView({ holder, blockedReason }: { holder: NearbyEntity | CombatLootable; blockedReason?: string | null }) {
  const { t } = useTranslation(["game"])
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const items = holder.loot_items ?? []
  const gold = holder.loot_gold ?? 0
  const isEmpty = items.length === 0 && gold === 0

  return (
    <div className="space-y-1" data-testid={`loot-${holder.id}`}>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="min-w-0 flex-1 truncate font-medium">{holder.name || holder.description}</span>
        <button
          className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
          disabled={waitingForAction || isEmpty || !!blockedReason}
          title={blockedReason ?? undefined}
          onClick={() => sendAction("take", { target_id: holder.id })}
        >
          {t("game:take_all")}
        </button>
      </div>
      {blockedReason && (
        <div className="text-[10px] text-muted-foreground" data-testid="loot-reason">
          {blockedReason}
        </div>
      )}

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
            <ItemDetails key={item.id} item={item} className="block min-w-0">
              <span className="block truncate text-xs">{item.name}</span>
            </ItemDetails>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Why a combat holder cannot be taken from right now: out of reach (frontend text keyed by
 * `reason_key`, else the server's localised `reason`), not the player's turn, or no Action left.
 */
function combatBlockedReason(
  t: (key: string, options?: Record<string, unknown>) => string,
  holder: CombatLootable,
  canAct: boolean,
  hasAction: boolean,
): string | null {
  if (!holder.in_reach) {
    const fallback = holder.reason ?? t("game:loot_reason_not_on_map")
    if (!holder.reason_key) return fallback
    return t(`game:loot_reason_${holder.reason_key}`, { defaultValue: fallback, dist: holder.distance_ft })
  }
  if (!canAct) return t("game:loot_not_your_turn")
  if (!hasAction) return t("game:loot_no_action")
  return null
}

export function LootPanel() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)
  const mode = useGameStore((s) => s.mode)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const budget = useGameStore((s) => s.budget)
  const [expanded, setExpanded] = useState(true)

  // Peaceful: lootable holders from `nearby`. Combat: `lootables`, each with its loot reach —
  // taking costs the Action and needs the holder in an adjacent cell.
  const isCombat = mode === "combat"
  const combatLootables = (isCombat && awareness && "lootables" in awareness ? awareness.lootables : undefined) ?? []
  const nearby = (!isCombat && awareness && "nearby" in awareness ? awareness.nearby : undefined) ?? []
  const peacefulLootables = nearby.filter((n) => "lootable" in n && n.lootable) as NearbyEntity[]
  if ((isCombat ? combatLootables.length : peacefulLootables.length) === 0) return null
  const hasAction = (budget?.actions ?? 0) > 0

  return (
    <div className="space-y-2" data-testid="loot-panel">
      <button
        className="flex w-full items-center gap-1 text-xs font-medium uppercase text-muted-foreground"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <Skull className="size-3" />
        {t("game:loot")}
        {isCombat && <span className="normal-case">· {t("game:loot_combat_cost")}</span>}
      </button>
      {expanded && (
        <div className="space-y-3">
          {isCombat
            ? combatLootables.map((holder) => (
                <LootView
                  key={holder.id}
                  holder={holder}
                  blockedReason={combatBlockedReason(t, holder, isMyTurn, hasAction)}
                />
              ))
            : peacefulLootables.map((holder) => <LootView key={holder.id} holder={holder} />)}
        </div>
      )}
    </div>
  )
}
