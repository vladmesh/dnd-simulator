import { useTranslation } from "react-i18next"
import type { TurnBudget } from "@/types/game"
import { Swords, Footprints, Zap, Shield } from "lucide-react"

interface BudgetDisplayProps {
  budget: TurnBudget
}

function Resource({
  icon: Icon,
  label,
  depleted,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  depleted: boolean
}) {
  return (
    <div className={`flex items-center gap-1 ${depleted ? "text-muted-foreground/50" : "text-muted-foreground"}`}>
      <Icon className="size-3" />
      <span>{label}</span>
    </div>
  )
}

export function BudgetDisplay({ budget }: BudgetDisplayProps) {
  const { t } = useTranslation(["game"])

  return (
    <div className="flex gap-3 text-xs">
      <Resource
        icon={Swords}
        label={t("game:actions_label", { n: budget.actions })}

        depleted={budget.actions <= 0}
      />
      <Resource
        icon={Zap}
        label={t("game:bonus_label", { n: budget.bonus_actions })}

        depleted={budget.bonus_actions <= 0}
      />
      <Resource
        icon={Footprints}
        label={t("game:movement_label", { n: budget.movement_remaining })}

        depleted={budget.movement_remaining <= 0}
      />
      <Resource
        icon={Shield}
        label={t("game:reaction_label", { n: budget.reaction })}

        depleted={budget.reaction <= 0}
      />
    </div>
  )
}
