interface Perceived {
  id: string
  description?: string
  name?: string
}

/**
 * Player-facing label for each perceived entity, keyed by its id.
 *
 * The id is an internal handle for actions and never becomes part of a label: the label is
 * what the server says the player perceives (`description`, e.g. a stranger's race), else the
 * known name, else a neutral fallback. Entities that would share a label (two goblins) get an
 * ordinal suffix in list order so every control stays uniquely addressable.
 */
export function perceivedLabels(
  entities: Perceived[],
  t: (key: string, opts?: Record<string, unknown>) => string,
): Map<string, string> {
  const base = entities.map((e) => e.description || e.name || t("game:unknown_creature"))
  const total = new Map<string, number>()
  for (const label of base) total.set(label, (total.get(label) ?? 0) + 1)
  const seen = new Map<string, number>()
  const result = new Map<string, string>()
  entities.forEach((e, i) => {
    const label = base[i]
    if ((total.get(label) ?? 0) < 2) {
      result.set(e.id, label)
      return
    }
    const n = (seen.get(label) ?? 0) + 1
    seen.set(label, n)
    result.set(e.id, t("game:target_ordinal", { target: label, n }))
  })
  return result
}
