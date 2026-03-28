import { useTranslation } from "react-i18next"
import { Backpack } from "lucide-react"
import { ActionDrawer } from "./ActionDrawer"
import { hasParam, getActionLabel } from "./utils"
import type { ActionInfo, ItemInfo } from "@/types/game"

interface InventoryDrawerProps {
  actions: ActionInfo[]
  items: ItemInfo[]
  isOpen: boolean
  onToggle: () => void
  disabled: boolean
  sendAction: (name: string, params?: Record<string, unknown>) => void
}

export function InventoryDrawer({ actions, items, isOpen, onToggle, disabled, sendAction }: InventoryDrawerProps) {
  const { t } = useTranslation(["game"])

  return (
    <ActionDrawer
      drawerKey="inventory"
      icon={<Backpack className="size-3.5" />}
      count={actions.length}
      isOpen={isOpen}
      onToggle={onToggle}
      disabled={disabled}
    >
      {actions.map((action) => {
        // For equip actions with weapon_id param, show weapon options
        if (hasParam(action, "weapon_id")) {
          const weapons = items.filter((i) => (i.item_type ?? i.type) === "weapon" || i.description.toLowerCase().includes("weapon"))
          return weapons.map((w) => (
            <button
              key={`${action.name}:${w.id}`}
              className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
              onClick={() => sendAction(action.name, { weapon_id: w.id })}
            >
              <span className="font-medium">{getActionLabel(t, action.name)}: {w.name}</span>
              {w.description && <span className="text-muted-foreground">{w.description}</span>}
            </button>
          ))
        }
        // Simple equip/unequip actions (armor, shield, etc.)
        return (
          <button
            key={action.name}
            className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
            onClick={() => sendAction(action.name)}
          >
            <span className="font-medium">{getActionLabel(t, action.name)}</span>
            <span className="text-muted-foreground">{action.description}</span>
          </button>
        )
      })}
    </ActionDrawer>
  )
}
