import { useCallback, useRef } from "react"
import type { MutableRefObject, RefObject } from "react"

interface UseStickyScroll {
  /** True while the user is pinned to the bottom of the container. */
  stickyRef: MutableRefObject<boolean>
  /** `onScroll` handler that updates the pinned flag. */
  handleScroll: () => void
}

/**
 * Track whether the user is pinned to the bottom of a scroll container.
 * Returns the pinned flag (as a ref) and the `onScroll` handler; the caller
 * decides how to scroll to the bottom (raw scrollTop vs virtualizer) in its
 * own effect gated on `stickyRef.current`.
 */
export function useStickyScroll(
  scrollRef: RefObject<HTMLElement | null>,
  threshold: number,
): UseStickyScroll {
  const stickyRef = useRef(true)

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    stickyRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  }, [scrollRef, threshold])

  return { stickyRef, handleScroll }
}
