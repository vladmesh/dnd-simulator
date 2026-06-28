import type { ResourcePoolInfo } from "@/types/game"

/** Extract spell slot level from pool id like "spell_slot_1" → 1. */
function parseSlotLevel(id: string): number | null {
  const match = id.match(/^spell_slot_(\d+)$/)
  return match ? parseInt(match[1], 10) : null
}

/** Get spell slots from resource pools (all spell_slot_* pools, including depleted). */
export function getSpellSlots(pools: ResourcePoolInfo[]): { level: number; pool: ResourcePoolInfo }[] {
  const result: { level: number; pool: ResourcePoolInfo }[] = []
  for (const pool of pools) {
    const level = parseSlotLevel(pool.id)
    if (level != null) {
      result.push({ level, pool })
    }
  }
  return result.sort((a, b) => a.level - b.level)
}
