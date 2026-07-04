import { useCallback, useState } from "react"
import type { EventDisplayEntry } from "@/lib/logProcessing"
import { extractAttackCardData } from "./attackCard"

/**
 * Shared interaction state for the event log: which aggregated-move rows are
 * expanded, and which attack row (if any) has its card modal open. Derives the
 * modal's card data from the selected entry.
 */
export function useLogInteraction() {
  const [expandedEntries, setExpandedEntries] = useState<Set<number>>(new Set())
  const [modalEntry, setModalEntry] = useState<EventDisplayEntry | null>(null)

  const toggleExpand = useCallback((idx: number) => {
    setExpandedEntries((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }, [])

  const cardData = modalEntry?.entry.event.data
    ? extractAttackCardData(modalEntry.entry.event.data)
    : null

  return { expandedEntries, toggleExpand, modalEntry, setModalEntry, cardData }
}
