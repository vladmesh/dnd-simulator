import { useTranslation } from "react-i18next"
import type { ResourcePoolInfo } from "@/types/game"

/** Extract spell slot level from pool id like "spell_slot_1" → 1. */
function parseSlotLevel(id: string): number | null {
  const match = id.match(/^spell_slot_(\d+)$/)
  return match ? parseInt(match[1], 10) : null
}

/** Get spell slots from resource pools (only spell_slot_* pools with remaining uses). */
export function getSpellSlots(pools: ResourcePoolInfo[]): { level: number; pool: ResourcePoolInfo }[] {
  const result: { level: number; pool: ResourcePoolInfo }[] = []
  for (const pool of pools) {
    const level = parseSlotLevel(pool.id)
    if (level != null && pool.current_uses > 0) {
      result.push({ level, pool })
    }
  }
  return result.sort((a, b) => a.level - b.level)
}

interface SmiteChoiceProps {
  onChoice: (slotLevel: number | null) => void
  onCancel: () => void
  slots: { level: number; pool: ResourcePoolInfo }[]
}

/** Inline smite choice panel — "Attack" or "Attack + Smite (slot N)". */
export function SmiteChoice({ onChoice, onCancel, slots }: SmiteChoiceProps) {
  const { t } = useTranslation("game")

  return (
    <div
      className="rounded border border-border bg-popover p-1 shadow-md"
      data-testid="smite-choice"
    >
      <button
        className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
        onClick={() => onChoice(null)}
      >
        {t("smite_attack_normal")}
      </button>
      {slots
        .filter(({ pool }) => pool.current_uses > 0)
        .map(({ level, pool }) => (
          <button
            key={level}
            className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
            onClick={() => onChoice(level)}
          >
            {t("smite_attack_with_smite", { level })}
            <span className="ml-1 text-muted-foreground">
              ({pool.current_uses}/{pool.max_uses})
            </span>
          </button>
        ))}
      <button
        className="mt-1 w-full rounded px-2 py-1 text-left text-xs text-muted-foreground hover:bg-accent"
        onClick={onCancel}
      >
        {t("cancel", { ns: "common" })}
      </button>
    </div>
  )
}
