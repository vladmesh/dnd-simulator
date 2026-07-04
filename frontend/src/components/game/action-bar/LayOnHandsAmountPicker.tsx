import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel, getButtonVariant } from "./utils"
import type { ResourcePoolInfo } from "@/types/game"
import { useGameStore } from "@/store/gameStore"

export interface LayOnHandsAmountPickerProps {
  name: string
  description: string
  costType?: string
  costClass: string
  dataAttrs: Record<string, string>
  disabled: boolean
  pool: ResourcePoolInfo
  targetId: string
  selfId?: string
  onConfirm: (amount: number) => void
  onCancel: () => void
  t: (key: string, opts?: Record<string, unknown>) => string
}

/** Slider/number amount picker for Lay on Hands, shown after a target is chosen. */
export function LayOnHandsAmountPicker({
  name,
  description,
  costType,
  costClass,
  dataAttrs,
  disabled,
  pool,
  targetId,
  selfId,
  onConfirm,
  onCancel,
  t,
}: LayOnHandsAmountPickerProps) {
  const awareness = useGameStore((s) => s.awareness)
  const player = useGameStore((s) => s.player)

  const selfHp = (awareness && "self_hp" in awareness ? awareness.self_hp : player?.hp) ?? null
  const selfMaxHp = (awareness && "self_max_hp" in awareness ? awareness.self_max_hp : player?.max_hp) ?? null
  const isSelfTarget = targetId === selfId
  const selfHpMissing = isSelfTarget && selfHp != null && selfMaxHp != null ? selfMaxHp - selfHp : null

  // For self: cap by min(pool, hp_missing). For allies: only pool cap — backend clamps further.
  const max =
    selfHpMissing != null ? Math.max(1, Math.min(pool.current_uses, selfHpMissing)) : pool.current_uses
  const [amount, setAmount] = useState<number>(1)

  const clamp = (n: number) => Math.max(1, Math.min(max, Math.floor(n)))
  const commit = () => onConfirm(clamp(amount))

  return (
    <div className="relative">
      <Button
        size="sm"
        variant={getButtonVariant(name, costType)}
        disabled={disabled}
        title={description}
        className={costClass}
        {...dataAttrs}
        onClick={onCancel}
      >
        {getActionLabel(t, name)}
        <ChevronDown className="ml-1 size-3" />
      </Button>
      <div
        className="absolute bottom-full left-0 z-10 mb-1 min-w-[220px] rounded border border-border bg-popover p-2 shadow-md"
        data-testid="lay-on-hands-amount"
        onKeyDown={(e) => {
          if (e.key === "Enter") commit()
        }}
      >
        <div className="mb-2 text-[10px] text-muted-foreground">
          {t("game:lay_on_hands_pool", { current: max, max: pool.max_uses })}
        </div>
        <div className="mb-2 flex items-center gap-2">
          <input
            type="range"
            min={1}
            max={max}
            value={clamp(amount)}
            onChange={(e) => setAmount(parseInt(e.target.value, 10))}
            className="flex-1"
            data-testid="lay-on-hands-slider"
          />
          <input
            type="number"
            min={1}
            max={max}
            value={amount}
            onChange={(e) => setAmount(e.target.value === "" ? 1 : parseInt(e.target.value, 10))}
            onBlur={() => setAmount(clamp(amount))}
            className="w-14 rounded border border-border bg-background px-1 py-0.5 text-xs"
            data-testid="lay-on-hands-input"
          />
        </div>
        <div className="flex justify-end gap-1">
          <button
            className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
            onClick={onCancel}
          >
            {t("common:cancel")}
          </button>
          <button
            className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            disabled={clamp(amount) < 1}
            onClick={commit}
            data-testid="lay-on-hands-confirm"
          >
            {t("game:lay_on_hands_heal", { amount: clamp(amount) })}
          </button>
        </div>
      </div>
    </div>
  )
}
