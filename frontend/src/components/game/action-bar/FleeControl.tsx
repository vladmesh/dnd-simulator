import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import type { ActionInfo, FleeStatus, TurnBudget } from "@/types/game"
import { getActionLabel, getCostTypeClass, isCostDepleted } from "./utils"

const DROPDOWN_KEY = "flee"

interface FleeControlProps {
  flee: FleeStatus
  /** The `flee` entry of `available_actions`; the server lists it only while fleeing is allowed. */
  action: ActionInfo | undefined
  disabled: boolean
  budget: TurnBudget | undefined
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
}

/** Localised travel time for a flee destination (whole minutes, hours past 60). */
function formatTravelTime(t: FleeControlProps["t"], seconds: number): string {
  const totalMinutes = Math.max(1, Math.ceil(seconds / 60))
  if (totalMinutes < 60) return t("game:flee_travel_minutes", { count: totalMinutes })
  return t("game:flee_travel_hours", { hours: Math.floor(totalMinutes / 60), minutes: totalMinutes % 60 })
}

/** Why fleeing is blocked: frontend text keyed by `reason_key`, else the server's localised `reason`. */
function fleeBlockedReason(t: FleeControlProps["t"], flee: FleeStatus): string {
  const fallback = flee.reason ?? t("game:flee_unavailable")
  if (!flee.reason_key) return fallback
  return t(`game:flee_reason_${flee.reason_key}`, { defaultValue: fallback })
}

/**
 * Why an allowed flee still cannot be taken: the server drops `flee` from `available_actions`
 * when the turn budget has no Action left, so name that before the generic fallback.
 */
function allowedButUnavailableReason(
  t: FleeControlProps["t"],
  action: ActionInfo | undefined,
  flee: FleeStatus,
  budget: TurnBudget | undefined,
): string | null {
  if (action != null && flee.destinations.length > 0) return null
  if (action == null && budget != null && budget.actions <= 0) return t("game:flee_reason_no_action")
  return t("game:flee_unavailable")
}

/**
 * Flee control driven by `awareness.flee`: always shown in combat, visibly disabled with
 * the reason while blocked; when allowed it opens a destination picker with nothing
 * preselected and sends `flee` only once the player picks a neighbour.
 */
export function FleeControl({ flee, action, disabled, budget, openDropdown, setOpenDropdown, sendAction, t }: FleeControlProps) {
  const costType = action?.cost_type
  const depleted = isCostDepleted(costType, budget)
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  const blockedReason = flee.allowed ? allowedButUnavailableReason(t, action, flee, budget) : fleeBlockedReason(t, flee)
  const isOpen = blockedReason == null && openDropdown === DROPDOWN_KEY

  return (
    <div className="relative flex items-center gap-2" data-testid="flee-control">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled || blockedReason != null}
        aria-expanded={isOpen}
        title={blockedReason ?? action?.description}
        className={getCostTypeClass(costType)}
        {...dataAttrs}
        onClick={() => setOpenDropdown(isOpen ? null : DROPDOWN_KEY)}
      >
        {getActionLabel(t, "flee")}
        {blockedReason == null && <ChevronDown className="ml-1 size-3" />}
      </Button>
      {blockedReason != null && (
        <span className="text-xs text-muted-foreground" data-testid="flee-reason">
          {blockedReason}
        </span>
      )}
      {isOpen && (
        <div
          role="menu"
          aria-label={t("game:flee_choose_destination")}
          className="absolute bottom-full left-0 z-10 mb-1 min-w-[200px] rounded border border-border bg-popover p-1 shadow-md"
        >
          <p className="px-2 py-1 text-xs text-muted-foreground">{t("game:flee_choose_destination")}</p>
          {flee.destinations.map((d) => (
            <button
              key={d.id}
              role="menuitem"
              className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-accent"
              onClick={() => sendAction("flee", { destination_id: d.id })}
            >
              <span>{d.name}</span>
              <span className="ml-auto text-muted-foreground">{formatTravelTime(t, d.travel_seconds)}</span>
            </button>
          ))}
          <button
            className="mt-1 w-full rounded border-t border-border px-2 py-1 text-left text-xs text-muted-foreground hover:bg-accent"
            onClick={() => setOpenDropdown(null)}
          >
            {t("common:cancel")}
          </button>
        </div>
      )}
    </div>
  )
}
