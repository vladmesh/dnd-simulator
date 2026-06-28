import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import type { ActionInfo, CombatAwareness, CostOption, ResourcePoolInfo } from "@/types/game"
import type { TurnBudget } from "@/types/game"
import { hasParam, getActionLabel, isCostDepleted, getButtonVariant, getCostTypeClass } from "./utils"
import { TargetDropdown } from "./TargetDropdown"
import { DirectionalDropdown } from "./DirectionalDropdown"
import { SayAction } from "./SayAction"

interface ActionButtonProps {
  action: ActionInfo
  nearby: CombatAwareness["nearby"]
  selfId?: string
  disabled: boolean
  budget: TurnBudget | undefined
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
  spellSlots?: ResourcePoolInfo[]
}

/** Label for a cost type (action / bonus_action). */
function costLabel(t: (key: string) => string, costType: string): string {
  const key = `game:cost_${costType}`
  const result = t(key)
  return result === key ? costType.replace("_", " ") : result
}

export function ActionButton({ action, nearby, selfId, disabled, budget, openDropdown, setOpenDropdown, sendAction, t, spellSlots }: ActionButtonProps) {
  const costOptions = action.cost_options
  const hasCostChoice = costOptions != null && costOptions.length > 1

  // When cost_options exist, show a cost choice dropdown first.
  // The selected cost_mode is injected into the sendAction params.
  if (hasCostChoice) {
    return (
      <CostChoiceButton
        action={action}
        costOptions={costOptions}
        nearby={nearby}
        selfId={selfId}
        disabled={disabled}
        budget={budget}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
        sendAction={sendAction}
        t={t}
      />
    )
  }

  return <CoreActionButton action={action} nearby={nearby} selfId={selfId} disabled={disabled} budget={budget} openDropdown={openDropdown} setOpenDropdown={setOpenDropdown} sendAction={sendAction} t={t} spellSlots={spellSlots} />
}

/** Standard action button — no cost choice. */
function CoreActionButton({ action, nearby, selfId, disabled, budget, openDropdown, setOpenDropdown, sendAction, t, spellSlots }: ActionButtonProps) {
  const { name } = action
  const costType = action.cost_type
  const depleted = isCostDepleted(costType, budget)
  const costClass = getCostTypeClass(costType)
  const dataAttrs: Record<string, string> = {}
  if (costType) dataAttrs["data-cost-type"] = costType
  if (depleted) dataAttrs["data-depleted"] = ""

  // target_mode === "single" → target dropdown with scope filtering.
  // Render even with empty nearby when scope includes self (ally/any), so self-target works.
  const scope = action.target_scope ?? "hostile"
  const selfTargetable = scope === "ally" || scope === "any"
  if (action.target_mode === "single" && (nearby.length > 0 || selfTargetable)) {
    return (
      <TargetDropdown
        name={name}
        description={action.description}
        nearby={nearby}
        scope={scope}
        selfId={selfId}
        disabled={disabled}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
        sendAction={sendAction}
        t={t}
        costType={costType}
        depleted={depleted}
        costClass={costClass}
        spellSlots={spellSlots}
      />
    )
  }

  // Fallback: legacy hasParam check for target_id (actions without target_mode set)
  if (action.target_mode == null && hasParam(action, "target_id") && nearby.length > 0) {
    return (
      <TargetDropdown
        name={name}
        description={action.description}
        nearby={nearby}
        scope="hostile"
        selfId={selfId}
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
  if ((hasParam(action, "toward") || hasParam(action, "direction")) && nearby.length > 0) {
    return (
      <DirectionalDropdown
        name={name}
        description={action.description}
        enemies={nearby}
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
