import type { ActionInfo } from "@/types/game"

const CORE_ACTIONS = new Set(["attack", "dodge", "dash", "disengage", "flee"])
const CONSUMABLE_ACTIONS = new Set(["use_item"])
const CLASS_FEATURE_ACTIONS = new Set(["second_wind", "bless", "lay_on_hands"])
const INVENTORY_ACTIONS = new Set([
  "equip", "unequip",
  "equip_armor", "unequip_armor",
  "equip_shield", "unequip_shield",
  "equip_head", "unequip_head",
  "equip_feet", "unequip_feet",
  "equip_ring", "unequip_ring",
])

export interface ActionGroups {
  core: ActionInfo[]
  consumables: ActionInfo[]
  classFeatures: ActionInfo[]
  inventory: ActionInfo[]
  other: ActionInfo[]
  endTurn: ActionInfo | undefined
}

export function categorizeActions(actions: ActionInfo[]): ActionGroups {
  const groups: ActionGroups = {
    core: [],
    consumables: [],
    classFeatures: [],
    inventory: [],
    other: [],
    endTurn: undefined,
  }

  for (const action of actions) {
    const { name } = action
    if (name === "end_turn") {
      groups.endTurn = action
    } else if (CORE_ACTIONS.has(name)) {
      groups.core.push(action)
    } else if (CONSUMABLE_ACTIONS.has(name)) {
      groups.consumables.push(action)
    } else if (CLASS_FEATURE_ACTIONS.has(name)) {
      groups.classFeatures.push(action)
    } else if (INVENTORY_ACTIONS.has(name)) {
      groups.inventory.push(action)
    } else {
      groups.other.push(action)
    }
  }

  return groups
}
