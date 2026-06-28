import { useTranslation } from "react-i18next"
import type { ResourcePoolInfo } from "@/types/game"

interface SmiteChoiceProps {
  onChoice: (slotLevel: number | null) => void
  onCancel: () => void
  slots: { level: number; pool: ResourcePoolInfo }[]
  targetName: string
}

/** Inline smite choice panel — "Attack <target>" or "Attack <target> + Smite (slot N)". */
export function SmiteChoice({ onChoice, onCancel, slots, targetName }: SmiteChoiceProps) {
  const { t } = useTranslation("game")

  return (
    <div
      className="rounded border border-border bg-popover p-1 shadow-md"
      role="menu"
      aria-label={t("smite_attack_normal", { target: targetName })}
      data-testid="smite-choice"
    >
      <button
        role="menuitem"
        className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
        onClick={() => onChoice(null)}
      >
        {t("smite_attack_normal", { target: targetName })}
      </button>
      {slots.map(({ level, pool }) => {
        const depleted = pool.current_uses <= 0
        return (
          <button
            key={level}
            role="menuitem"
            className={`w-full rounded px-2 py-1 text-left text-xs ${depleted ? "opacity-50 cursor-not-allowed" : "hover:bg-accent"}`}
            disabled={depleted}
            onClick={() => onChoice(level)}
          >
            {t("smite_attack_with_smite", { level, target: targetName })}
            <span className="ml-1 text-muted-foreground">
              ({pool.current_uses}/{pool.max_uses})
            </span>
          </button>
        )
      })}
      <button
        role="menuitem"
        className="mt-1 w-full rounded px-2 py-1 text-left text-xs text-muted-foreground hover:bg-accent"
        onClick={onCancel}
      >
        {t("cancel", { ns: "common" })}
      </button>
    </div>
  )
}
