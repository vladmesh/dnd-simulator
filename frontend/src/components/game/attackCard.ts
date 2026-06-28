import type { AttackCardData } from "./AttackCardModal"
import type { AttackRollData, DamageComponentData } from "@/types/game"
import { hasAttackBreakdown } from "@/lib/logProcessing"

/** Extract AttackCardData from raw event data. */
export function extractAttackCardData(
  data: Record<string, unknown>,
): AttackCardData | null {
  if (!hasAttackBreakdown(data)) return null

  const attackRoll = data.attack_roll as AttackRollData
  const damageComponents = Array.isArray(data.damage_components)
    ? (data.damage_components as DamageComponentData[])
    : undefined

  return {
    attackerName: (data.attacker_name as string) ?? (data.attacker_id as string) ?? "?",
    targetName: (data.target_name as string) ?? (data.target_id as string) ?? "?",
    weapon: (data.weapon as string) ?? "Attack",
    hit: data.hit === true,
    critical: data.critical === true,
    ac: typeof data.ac === "number" ? data.ac : 0,
    attackRoll,
    totalDamage: typeof data.damage === "number" ? data.damage : undefined,
    rolledDamage: typeof data.total_damage === "number" ? data.total_damage : undefined,
    damageComponents,
  }
}
