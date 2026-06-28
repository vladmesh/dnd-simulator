import { useEffect, useState } from "react"
import type { RefOption } from "@/types/api"

interface RefSelectProps {
  id: string
  worldId: string
  refType: string
  value: string
  onChange: (value: string) => void
  fetchRefs: (worldId: string, refType: string) => Promise<RefOption[]>
}

// Simple in-memory cache for ref options (key = worldId:refType)
const refCache = new Map<string, RefOption[]>()
// Keys whose fetch has settled (success or error) — avoids refetch and stuck loading
const refAttempted = new Set<string>()

export function RefSelect({
  id,
  worldId,
  refType,
  value,
  onChange,
  fetchRefs,
}: RefSelectProps) {
  const [, forceRerender] = useState(0)
  const cacheKey = `${worldId}:${refType}`
  const cached = refCache.get(cacheKey)
  const options = cached ?? []
  const loading = cached === undefined && !refAttempted.has(cacheKey)

  useEffect(() => {
    if (refCache.has(cacheKey) || refAttempted.has(cacheKey)) return
    let active = true
    fetchRefs(worldId, refType)
      .then((data) => {
        refCache.set(cacheKey, data)
      })
      .finally(() => {
        refAttempted.add(cacheKey)
        if (active) forceRerender((n) => n + 1)
      })
    return () => {
      active = false
    }
  }, [cacheKey, worldId, refType, fetchRefs])

  return (
    <select
      id={id}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading}
      className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm"
      aria-label={undefined}
    >
      <option value="">{loading ? "Loading…" : "—"}</option>
      {options.map((opt) => (
        <option key={opt.id} value={opt.id}>
          {opt.name} ({opt.id})
        </option>
      ))}
    </select>
  )
}

