import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel, getButtonVariant } from "./utils"
import type { ResourcePoolInfo } from "@/types/game"
import { getSpellSlots } from "../SmiteChoice"
import { useGameStore } from "@/store/gameStore"

interface TargetDropdownProps {
  name: string
  description: string
  nearby: { id: string; distance_ft?: number; is_hostile?: boolean }[]
  scope: string
  selfId?: string
  disabled: boolean
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
  costType?: string
  depleted: boolean
  costClass: string
  spellSlots?: ResourcePoolInfo[]
}

interface TargetEntry {
  id: string
  label: string
  distance_ft?: number
}

function buildTargets(
  actionName: string,
  nearby: TargetDropdownProps["nearby"],
  scope: string,
  selfId: string | undefined,
  t: TargetDropdownProps["t"],
): TargetEntry[] {
  const targets: TargetEntry[] = []

  // Add self for ally/any scopes
  if ((scope === "ally" || scope === "any") && selfId) {
    targets.push({
      id: selfId,
      label: t("game:target_self"),
    })
  }

  for (const e of nearby) {
    if (scope === "hostile" && !e.is_hostile) continue
    if (scope === "ally" && e.is_hostile) continue
    
    let label = e.id
    if (actionName === "attack") {
      label = t("game:attack_target", { target: e.id })
    } else if (actionName === "talk") {
      label = t("game:talk_to", { target: e.id })
    }

    targets.push({
      id: e.id,
      label,
      distance_ft: e.distance_ft,
    })
  }

  return targets
}

export function TargetDropdown({ name, description, nearby, scope, selfId, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass, spellSlots }: TargetDropdownProps) {
  const [smiteTargetId, setSmiteTargetId] = useState<string | null>(null)
  const [layTargetId, setLayTargetId] = useState<string | null>(null)
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  const targets = buildTargets(name, nearby, scope, selfId, t)

  // Check if this is an attack action with available spell slots
  const isAttack = name === "attack"
  const slots = isAttack && spellSlots ? getSpellSlots(spellSlots) : []
  const hasSmiteOption = slots.length > 0

  const isLayOnHands = name === "lay_on_hands"
  const layPool = isLayOnHands ? spellSlots?.find((p) => p.id === "lay_on_hands") : undefined

  const handleTargetSelected = (targetId: string) => {
    if (hasSmiteOption) {
      // Show smite choice instead of sending immediately
      setSmiteTargetId(targetId)
      setOpenDropdown(`${name}-smite`)
    } else if (isLayOnHands) {
      setLayTargetId(targetId)
      setOpenDropdown(`${name}-amount`)
    } else {
      sendAction(name, { target_id: targetId })
    }
  }

  const handleLayAmount = (amount: number) => {
    if (!layTargetId) return
    sendAction(name, { target_id: layTargetId, amount })
    setLayTargetId(null)
    setOpenDropdown(null)
  }

  const handleSmiteChoice = (slotLevel: number | null) => {
    if (!smiteTargetId) return
    const params: Record<string, unknown> = { target_id: smiteTargetId }
    if (slotLevel != null) {
      params.smite_slot_level = slotLevel
    }
    sendAction(name, params)
    setSmiteTargetId(null)
  }

  // Lay on Hands amount picker (shown after target is selected)
  if (layTargetId && openDropdown === `${name}-amount` && layPool) {
    return (
      <LayOnHandsAmountPicker
        name={name}
        description={description}
        costType={costType}
        costClass={costClass}
        dataAttrs={dataAttrs}
        disabled={disabled}
        pool={layPool}
        targetId={layTargetId}
        selfId={selfId}
        onConfirm={handleLayAmount}
        onCancel={() => {
          setLayTargetId(null)
          setOpenDropdown(null)
        }}
        t={t}
      />
    )
  }

  // Smite choice panel (shown after target is selected)
  if (smiteTargetId && openDropdown === `${name}-smite`) {
    return (
      <div className="relative">
        <Button
          size="sm"
          variant={getButtonVariant(name, costType)}
          disabled={disabled}
          title={description}
          className={costClass}
          {...dataAttrs}
          aria-haspopup="menu"
          aria-expanded={true}
          onClick={() => {
            setSmiteTargetId(null)
            setOpenDropdown(null)
          }}
        >
          {getActionLabel(t, name)}
          <ChevronDown className="ml-1 size-3" />
        </Button>
        <div
          className="absolute bottom-full left-0 z-10 mb-1 min-w-[200px] rounded border border-border bg-popover p-1 shadow-md"
          role="menu"
          aria-label={t("game:smite_attack_normal", { target: smiteTargetId })}
          data-testid="smite-choice"
        >
          <button
            role="menuitem"
            className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
            onClick={() => handleSmiteChoice(null)}
          >
            {t("game:smite_attack_normal", { target: smiteTargetId })}
          </button>
          {slots.map(({ level, pool }) => {
            const depleted = pool.current_uses <= 0
            return (
              <button
                key={level}
                role="menuitem"
                className={`w-full rounded px-2 py-1 text-left text-xs ${depleted ? "opacity-50 cursor-not-allowed" : "hover:bg-accent"}`}
                disabled={depleted}
                onClick={() => handleSmiteChoice(level)}
              >
                {t("game:smite_attack_with_smite", { level, target: smiteTargetId })}
                <span className="ml-1 text-muted-foreground">
                  ({pool.current_uses}/{pool.max_uses})
                </span>
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  const hasMenu = targets.length > 1
  const isOpen = openDropdown === name && hasMenu
  return (
    <div className="relative">
      <Button
        size="sm"
        variant={getButtonVariant(name, costType)}
        disabled={disabled}
        title={description}
        className={costClass}
        {...dataAttrs}
        aria-haspopup={hasMenu ? "menu" : undefined}
        aria-expanded={hasMenu ? isOpen : undefined}
        onClick={() => {
          if (targets.length === 1) {
            handleTargetSelected(targets[0].id)
          } else {
            setOpenDropdown(openDropdown === name ? null : name)
          }
        }}
      >
        {getActionLabel(t, name)}
        {hasMenu && <ChevronDown className="ml-1 size-3" />}
      </Button>
      {isOpen && (
        <div
          className="absolute bottom-full left-0 z-10 mb-1 min-w-[160px] rounded border border-border bg-popover p-1 shadow-md"
          role="menu"
          aria-label={description}
        >
          {targets.map((entry) => (
            <button
              key={entry.id}
              role="menuitem"
              className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
              onClick={() => handleTargetSelected(entry.id)}
            >
              {entry.label}
              {entry.distance_ft != null && (
                <span className="ml-1 text-muted-foreground">({entry.distance_ft}ft)</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

interface LayOnHandsAmountPickerProps {
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
  t: TargetDropdownProps["t"]
}

function LayOnHandsAmountPicker({
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
