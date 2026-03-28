import { useTranslation } from "react-i18next"
import { FlaskConical } from "lucide-react"
import { ActionDrawer } from "./ActionDrawer"
import type { ItemInfo } from "@/types/game"

interface ConsumableDrawerProps {
  items: ItemInfo[]
  isOpen: boolean
  onToggle: () => void
  disabled: boolean
  sendAction: (name: string, params?: Record<string, unknown>) => void
}

export function ConsumableDrawer({ items, isOpen, onToggle, disabled, sendAction }: ConsumableDrawerProps) {
  const { t } = useTranslation(["game"])

  return (
    <ActionDrawer
      drawerKey="consumables"
      icon={<FlaskConical className="size-3.5" />}
      count={items.length}
      isOpen={isOpen}
      onToggle={onToggle}
      disabled={disabled}
      title={t("game:consumables_tooltip", "Consumable items")}
    >
      {items.map((item) => (
        <button
          key={item.id}
          className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
          onClick={() => sendAction("use_item", { item_id: item.id })}
        >
          <span className="font-medium">{item.name}</span>
          {item.description && (
            <span className="text-muted-foreground">{item.description}</span>
          )}
        </button>
      ))}
    </ActionDrawer>
  )
}
