import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel, getButtonVariant } from "./utils"
import type { ResourcePoolInfo } from "@/types/game"

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
    // "any" → include everyone
    targets.push({
      id: e.id,
      label: t("game:attack_target", { target: e.id }),
      distance_ft: e.distance_ft,
    })
  }

  return targets
}

/** Extract spell slot level from pool id like "spell_slot_1" → 1. */
function parseSlotLevel(id: string): number | null {
  const match = id.match(/^spell_slot_(\d+)$/)
  return match ? parseInt(match[1], 10) : null
}

/** Get spell slots from resource pools (only spell_slot_* pools). */
function getSpellSlots(pools: ResourcePoolInfo[]): { level: number; pool: ResourcePoolInfo }[] {
  const result: { level: number; pool: ResourcePoolInfo }[] = []
  for (const pool of pools) {
    const level = parseSlotLevel(pool.id)
    if (level != null) {
      result.push({ level, pool })
    }
  }
  return result.sort((a, b) => a.level - b.level)
}

export function TargetDropdown({ name, description, nearby, scope, selfId, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass, spellSlots }: TargetDropdownProps) {
  const [smiteTargetId, setSmiteTargetId] = useState<string | null>(null)
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  const targets = buildTargets(nearby, scope, selfId, t)

  // Check if this is an attack action with available spell slots
  const isAttack = name === "attack"
  const slots = isAttack && spellSlots ? getSpellSlots(spellSlots) : []
  const hasSmiteOption = slots.length > 0

  const handleTargetSelected = (targetId: string) => {
    if (hasSmiteOption) {
      // Show smite choice instead of sending immediately
      setSmiteTargetId(targetId)
      setOpenDropdown(`${name}-smite`)
    } else {
      sendAction(name, { target_id: targetId })
    }
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
          data-testid="smite-choice"
        >
          <button
            className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
            onClick={() => handleSmiteChoice(null)}
          >
            {t("game:smite_attack_normal")}
          </button>
          {slots.map(({ level, pool }) => {
            const isDepleted = pool.current_uses === 0
            return (
              <button
                key={level}
                className={`w-full rounded px-2 py-1 text-left text-xs hover:bg-accent ${isDepleted ? "opacity-40" : ""}`}
                disabled={isDepleted}
                onClick={() => handleSmiteChoice(level)}
              >
                {t("game:smite_attack_with_smite", { level })}
                {!isDepleted && (
                  <span className="ml-1 text-muted-foreground">
                    ({pool.current_uses}/{pool.max_uses})
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <Button
        size="sm"
        variant={getButtonVariant(name, costType)}
        disabled={disabled}
        title={description}
        className={costClass}
        {...dataAttrs}
        onClick={() => {
          if (targets.length === 1) {
            handleTargetSelected(targets[0].id)
          } else {
            setOpenDropdown(openDropdown === name ? null : name)
          }
        }}
      >
        {getActionLabel(t, name)}
        {targets.length > 1 && <ChevronDown className="ml-1 size-3" />}
      </Button>
      {openDropdown === name && targets.length > 1 && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[160px] rounded border border-border bg-popover p-1 shadow-md">
          {targets.map((entry) => (
            <button
              key={entry.id}
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
