import { useTranslation } from "react-i18next"
import { Sparkles } from "lucide-react"
import { ActionDrawer } from "./ActionDrawer"
import { getActionLabel } from "./utils"
import type { ActionInfo } from "@/types/game"

interface ClassFeatureDrawerProps {
  actions: ActionInfo[]
  isOpen: boolean
  onToggle: () => void
  disabled: boolean
  sendAction: (name: string, params?: Record<string, unknown>) => void
}

export function ClassFeatureDrawer({ actions, isOpen, onToggle, disabled, sendAction }: ClassFeatureDrawerProps) {
  const { t } = useTranslation(["game"])

  return (
    <ActionDrawer
      drawerKey="class-features"
      icon={<Sparkles className="size-3.5" />}
      count={actions.length}
      isOpen={isOpen}
      onToggle={onToggle}
      disabled={disabled}
    >
      {actions.map((action) => (
        <button
          key={action.name}
          className="flex w-full flex-col gap-0.5 rounded px-3 py-1.5 text-left text-xs hover:bg-accent"
          onClick={() => sendAction(action.name)}
        >
          <span className="flex items-center gap-2 font-medium">
            {getActionLabel(t, action.name)}
            {action.cost_type && (
              <span className="rounded bg-muted px-1 text-[10px] text-muted-foreground">
                {action.cost_type}
              </span>
            )}
          </span>
          <span className="text-muted-foreground">{action.description}</span>
        </button>
      ))}
    </ActionDrawer>
  )
}
