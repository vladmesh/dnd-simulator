import { useTranslation } from "react-i18next"
import { Sparkles } from "lucide-react"
import { ActionDrawer } from "./ActionDrawer"
import { ActionButton } from "./ActionButton"
import type { ActionInfo, CombatAwareness, TurnBudget, ResourcePoolInfo } from "@/types/game"

interface ClassFeatureDrawerProps {
  actions: ActionInfo[]
  isOpen: boolean
  onToggle: () => void
  disabled: boolean
  nearby: CombatAwareness["nearby"]
  selfId?: string
  budget: TurnBudget | undefined
  openDropdown: string | null
  setOpenDropdown: (v: string | null) => void
  sendAction: (name: string, params?: Record<string, unknown>) => void
  spellSlots?: ResourcePoolInfo[]
}

export function ClassFeatureDrawer({ actions, isOpen, onToggle, disabled, nearby, selfId, budget, openDropdown, setOpenDropdown, sendAction, spellSlots }: ClassFeatureDrawerProps) {
  const { t } = useTranslation(["game"])

  return (
    <ActionDrawer
      drawerKey="class-features"
      icon={<Sparkles className="size-3.5" />}
      count={actions.length}
      isOpen={isOpen}
      onToggle={onToggle}
      disabled={disabled}
      title={t("game:drawer_class_features", "Class Features")}
    >
      {actions.map((action) => (
        <ActionButton
          key={action.name}
          action={action}
          nearby={nearby}
          selfId={selfId}
          disabled={disabled}
          budget={budget}
          openDropdown={openDropdown}
          setOpenDropdown={setOpenDropdown}
          sendAction={sendAction}
          t={t}
          spellSlots={spellSlots}
        />
      ))}
    </ActionDrawer>
  )
}
