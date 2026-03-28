import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import { getActionLabel } from "./utils"

interface DirectionalDropdownProps {
  name: string
  description: string
  enemies: { id: string }[]
  disabled: boolean
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
  costType?: string
  depleted: boolean
  costClass: string
}

export function DirectionalDropdown({ name, description, enemies, disabled, openDropdown, setOpenDropdown, sendAction, t, costType, depleted, costClass }: DirectionalDropdownProps) {
  const towardKey = name === "dash" ? "game:dash_toward" : "game:move_toward"
  const awayKey = name === "dash" ? "game:dash_away" : "game:move_away"
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        title={description}
        className={costClass}
        {...dataAttrs}
        onClick={() => setOpenDropdown(openDropdown === name ? null : name)}
      >
        {getActionLabel(t, name)}
        <ChevronDown className="ml-1 size-3" />
      </Button>
      {openDropdown === name && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[180px] rounded border border-border bg-popover p-1 shadow-md">
          {enemies.map((e) => (
            <div key={e.id} className="flex gap-1">
              <button
                className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                onClick={() => sendAction(name, { toward: e.id })}
              >
                {t(towardKey, { target: e.id })}
              </button>
              <button
                className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                onClick={() => sendAction(name, { away_from: e.id })}
              >
                {t(awayKey, { target: e.id })}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
