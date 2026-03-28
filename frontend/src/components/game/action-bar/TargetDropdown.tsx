import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel, getButtonVariant } from "./utils"

interface TargetDropdownProps {
  name: string
  description: string
  enemies: { id: string; distance_ft?: number }[]
  disabled: boolean
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
  costType?: string
  depleted: boolean
  costClass: string
}

export function TargetDropdown({ name, description, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass }: TargetDropdownProps) {
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

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
          if (enemies.length === 1) {
            sendAction(name, { target_id: enemies[0].id })
          } else {
            setOpenDropdown(openDropdown === name ? null : name)
          }
        }}
      >
        {getActionLabel(t, name)}
        {enemies.length > 1 && <ChevronDown className="ml-1 size-3" />}
      </Button>
      {openDropdown === name && enemies.length > 1 && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[160px] rounded border border-border bg-popover p-1 shadow-md">
          {enemies.map((e) => (
            <button
              key={e.id}
              className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
              onClick={() => sendAction(name, { target_id: e.id })}
            >
              {t("game:attack_target", { target: e.id })}
              {e.distance_ft != null && (
                <span className="ml-1 text-muted-foreground">({e.distance_ft}ft)</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
