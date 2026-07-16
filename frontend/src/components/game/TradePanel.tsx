import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { wsClient } from "@/transport/wsClient"
import { ChevronDown, ChevronRight, ShoppingBag, Coins } from "lucide-react"
import type { MerchantInfo } from "@/types/game"
import { ItemDetails } from "./ItemDetails"

function sendAction(name: string, params?: Record<string, unknown>) {
  wsClient.send({ type: "action", name, params })
  useGameStore.getState().setWaitingForAction(true)
}

export function MerchantView({ merchant }: { merchant: MerchantInfo }) {
  const { t } = useTranslation(["game"])
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const player = useGameStore((s) => s.player)
  const playerGold = player?.gold ?? 0
  const inventory = player?.inventory ?? []
  const sellableItems = inventory.filter((i) => i.price != null && i.price > 0)

  return (
    <div className="space-y-2">
      {/* Merchant header */}
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">{merchant.name}</span>
        <span className="flex items-center gap-1 text-muted-foreground">
          <Coins className="size-3" />
          {merchant.gold}g
        </span>
      </div>

      {/* Buy section — merchant's items */}
      {merchant.items.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase text-muted-foreground">{t("game:buy")}</div>
          <div className="max-h-32 space-y-0.5 overflow-y-auto">
            {merchant.items.map((item) => (
              <div key={item.id} className="flex items-center gap-1 text-xs">
                <ItemDetails item={item} className="min-w-0 flex-1">
                  <span className="block truncate">
                    {item.name}
                    {item.price != null && (
                      <span className="ml-1 text-muted-foreground">{item.price}g</span>
                    )}
                  </span>
                </ItemDetails>
                <button
                  className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
                  disabled={waitingForAction || (item.price != null && playerGold < item.price)}
                  onClick={() => sendAction("buy", { merchant_id: merchant.id, item_id: item.id })}
                >
                  {t("game:buy")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sell section — player's items with prices */}
      {sellableItems.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase text-muted-foreground">{t("game:sell")}</div>
          <div className="max-h-32 space-y-0.5 overflow-y-auto">
            {sellableItems.map((item) => (
              <div key={item.id} className="flex items-center gap-1 text-xs">
                <ItemDetails item={item} className="min-w-0 flex-1">
                  <span className="block truncate">
                    {item.name}
                    <span className="ml-1 text-muted-foreground">{item.price}g</span>
                  </span>
                </ItemDetails>
                <button
                  className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] hover:bg-accent/80 disabled:opacity-50"
                  disabled={waitingForAction || merchant.gold < (item.price ?? 0)}
                  onClick={() => sendAction("sell", { merchant_id: merchant.id, item_id: item.id })}
                >
                  {t("game:sell")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function TradePanel() {
  const { t } = useTranslation(["game"])
  const awareness = useGameStore((s) => s.awareness)
  const [expanded, setExpanded] = useState(true)

  // Only show in peaceful mode when merchants are nearby
  const merchants = (awareness && "merchants" in awareness ? awareness.merchants : undefined) ?? []
  if (merchants.length === 0) return null

  return (
    <div className="space-y-2">
      <button
        className="flex w-full items-center gap-1 text-xs font-medium uppercase text-muted-foreground"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <ShoppingBag className="size-3" />
        {t("game:trade")}
      </button>
      {expanded && (
        <div className="space-y-3">
          {merchants.map((m) => (
            <MerchantView key={m.id} merchant={m} />
          ))}
        </div>
      )}
    </div>
  )
}
