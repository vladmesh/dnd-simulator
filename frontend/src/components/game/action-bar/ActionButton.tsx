import { Button } from "@/components/ui/button"
import type { ActionInfo, CombatAwareness } from "@/types/game"
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

export function ActionButton({ action, enemies, disabled, budget, openDropdown, setOpenDropdown, sendAction, t }: ActionButtonProps) {
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
