import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel, getButtonVariant } from "./utils"
import type { ResourcePoolInfo } from "@/types/game"
import { getSpellSlots } from "../spellSlots"
import { SmiteChoice } from "../SmiteChoice"
import { buildAttackParams } from "../attackParams"
import { LayOnHandsAmountPicker } from "./LayOnHandsAmountPicker"

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
    sendAction(name, buildAttackParams(smiteTargetId, slotLevel))
    setSmiteTargetId(null)
    setOpenDropdown(null)
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
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[200px]">
          <SmiteChoice
            slots={slots}
            targetName={smiteTargetId}
            onChoice={handleSmiteChoice}
            onCancel={() => {
              setSmiteTargetId(null)
              setOpenDropdown(null)
            }}
          />
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
