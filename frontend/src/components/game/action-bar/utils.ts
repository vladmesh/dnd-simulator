import type { ActionInfo, TurnBudget } from "@/types/game"

/** Check if an action has a specific param by name. */
export function hasParam(action: ActionInfo, paramName: string): boolean {
  return action.params.some((p) => p.name === paramName)
}

export function getActionLabel(t: (key: string) => string, name: string): string {
  const key = `game:${name}`
  const result = t(key)
  return result === key ? name : result
}

/** Check if the cost type's budget is depleted. */
export function isCostDepleted(costType: string | undefined, budget: TurnBudget | undefined): boolean {
  if (!budget || !costType) return false
  switch (costType) {
    case "action": return budget.actions <= 0
    case "bonus_action": return budget.bonus_actions <= 0
    case "movement": return budget.movement_remaining <= 0
    default: return false
  }
}

/** Get button variant based on action name and cost type. */
export function getButtonVariant(name: string, costType: string | undefined): "destructive" | "secondary" | "outline" {
  if (name === "attack") return "destructive"
  if (name === "end_turn") return "outline"
  if (costType === "bonus_action") return "secondary"
  return "secondary"
}

/** Get cost-type specific className. */
export function getCostTypeClass(costType: string | undefined): string {
  if (costType === "bonus_action") return "ring-1 ring-amber-400/60 text-amber-200"
  if (costType === "free") return "opacity-80"
  return ""
}
