import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import type { ActionInfo, CombatAwareness, CostOption } from "@/types/game"
import type { TurnBudget } from "@/types/game"
import { hasParam, getActionLabel, isCostDepleted, getButtonVariant, getCostTypeClass } from "./utils"
import { TargetDropdown } from "./TargetDropdown"
import { DirectionalDropdown } from "./DirectionalDropdown"
import { SayAction } from "./SayAction"

interface ActionButtonProps {
  action: ActionInfo
  enemies: CombatAwareness["nearby"]
  disabled: boolean
  budget: TurnBudget | undefined
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
}

/** Label for a cost type (action / bonus_action). */
function costLabel(t: (key: string) => string, costType: string): string {
  const key = `game:cost_${costType}`
  const result = t(key)
  return result === key ? costType.replace("_", " ") : result
}

export function ActionButton({ action, enemies, disabled, budget, openDropdown, setOpenDropdown, sendAction, t }: ActionButtonProps) {
  const { name } = action
  const costOptions = action.cost_options
  const hasCostChoice = costOptions != null && costOptions.length > 1

  // When cost_options exist, show a cost choice dropdown first.
  // The selected cost_mode is injected into the sendAction params.
  if (hasCostChoice) {
    return (
      <CostChoiceButton
        action={action}
        costOptions={costOptions}
        enemies={enemies}
        disabled={disabled}
        budget={budget}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
        sendAction={sendAction}
        t={t}
      />
    )
  }

  return <CoreActionButton action={action} enemies={enemies} disabled={disabled} budget={budget} openDropdown={openDropdown} setOpenDropdown={setOpenDropdown} sendAction={sendAction} t={t} />
}

/** Standard action button — no cost choice. */
function CoreActionButton({ action, enemies, disabled, budget, openDropdown, setOpenDropdown, sendAction, t }: ActionButtonProps) {
  const { name } = action
  const costType = action.cost_type
  const depleted = isCostDepleted(costType, budget)
  const costClass = getCostTypeClass(costType)
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  // Has target_id param → target dropdown
  if (hasParam(action, "target_id") && enemies.length > 0) {
    return (
      <TargetDropdown
        name={name}
        description={action.description}
        enemies={enemies}
        disabled={disabled}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
        sendAction={sendAction}
        t={t}
        costType={costType}
        depleted={depleted}
        costClass={costClass}
      />
    )
  }

  // Has toward/away_from/direction params → directional dropdown
  if ((hasParam(action, "toward") || hasParam(action, "direction")) && enemies.length > 0) {
    return (
      <DirectionalDropdown
        name={name}
        description={action.description}
        enemies={enemies}
        disabled={disabled}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
        sendAction={sendAction}
        t={t}
        costType={costType}
        depleted={depleted}
        costClass={costClass}
      />
    )
  }

  // Say — needs text input
  if (name === "say") {
    return (
      <SayAction
        description={action.description}
        disabled={disabled}
        sendAction={sendAction}
        t={t}
      />
    )
  }

  // Simple button — no special params
  return (
    <Button
      size="sm"
      variant={getButtonVariant(name, costType)}
      disabled={disabled}
      title={action.description}
      className={costClass}
      {...dataAttrs}
      onClick={() => {
        if (name === "wait") {
          sendAction("wait", { hours: 1 })
        } else {
          sendAction(name)
        }
      }}
    >
      {getActionLabel(t, name)}
    </Button>
  )
}

/** Action button with cost choice dropdown — shows cost options, then delegates to CoreActionButton. */
function CostChoiceButton({
  action,
  costOptions,
  enemies,
  disabled,
  budget,
  openDropdown,
  setOpenDropdown,
  sendAction,
  t,
}: ActionButtonProps & { costOptions: CostOption[] }) {
  const { name } = action
  const dropdownKey = `${name}-cost`
  const isOpen = openDropdown === dropdownKey

  // Default to the first (cheapest/most useful) cost type for display
  const defaultCostType = action.cost_type
  const depleted = costOptions.every((opt) => isCostDepleted(opt.cost_type, budget))
  const costClass = getCostTypeClass(defaultCostType)
  const dataAttrs: Record<string, string> = {}
  if (defaultCostType) dataAttrs["data-cost-type"] = defaultCostType
  if (depleted) dataAttrs["data-depleted"] = ""

  return (
    <div className="relative">
      <Button
        size="sm"
        variant={getButtonVariant(name, defaultCostType)}
        disabled={disabled}
        title={action.description}
        className={costClass}
        {...dataAttrs}
        onClick={() => setOpenDropdown(isOpen ? null : dropdownKey)}
      >
        {getActionLabel(t, name)}
        <ChevronDown className="ml-1 size-3" />
      </Button>
      {isOpen && (
        <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[140px] rounded border border-border bg-popover p-1 shadow-md">
          {costOptions.map((opt) => {
            const optDepleted = isCostDepleted(opt.cost_type, budget)
            return (
              <button
                key={opt.cost_type}
                className={`w-full rounded px-2 py-1 text-left text-xs hover:bg-accent ${optDepleted ? "opacity-40" : ""}`}
                disabled={optDepleted}
                onClick={() => {
                  const costMode = opt.source === "default" ? undefined : opt.cost_type
                  const params: Record<string, unknown> = {}
                  if (costMode) params.cost_mode = costMode
                  sendAction(name, params)
                  setOpenDropdown(null)
                }}
              >
                <span className="flex items-center gap-2">
                  <span className={getCostTypeClass(opt.cost_type)}>
                    {costLabel(t, opt.cost_type)}
                  </span>
                  {opt.source !== "default" && (
                    <span className="text-[10px] text-muted-foreground">({opt.source.replace("_", " ")})</span>
                  )}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
