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

export function RefSelect({
  id,
  worldId,
  refType,
  value,
  onChange,
  fetchRefs,
}: RefSelectProps) {
  const [options, setOptions] = useState<RefOption[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const cacheKey = `${worldId}:${refType}`
    const cached = refCache.get(cacheKey)
    if (cached) {
      setOptions(cached)
      return
    }

    setLoading(true)
    fetchRefs(worldId, refType)
      .then((data) => {
        refCache.set(cacheKey, data)
        setOptions(data)
      })
      .finally(() => setLoading(false))
  }, [worldId, refType, fetchRefs])

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

