/** Build wire params for an `attack` action, optionally with a Divine Smite slot. */
export function buildAttackParams(
  targetId: string,
  slotLevel: number | null,
): Record<string, unknown> {
  const params: Record<string, unknown> = { target_id: targetId }
  if (slotLevel != null) {
    params.smite_slot_level = slotLevel
  }
  return params
}
