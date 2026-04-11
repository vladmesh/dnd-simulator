import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel, getButtonVariant } from "./utils"

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

export function TargetDropdown({ name, description, nearby, scope, selfId, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass }: TargetDropdownProps) {
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  const targets = buildTargets(nearby, scope, selfId, t)

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
            sendAction(name, { target_id: targets[0].id })
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
              onClick={() => sendAction(name, { target_id: entry.id })}
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
