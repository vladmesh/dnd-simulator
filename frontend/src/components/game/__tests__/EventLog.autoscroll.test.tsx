import { act, fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from "vitest"
import { useGameStore } from "@/store/gameStore"
import { EventLog } from "../EventLog"
import type { PerceivedEvent } from "@/types/game"
import type { LogEntry } from "@/store/slices/logSlice"

// Spy on the virtualizer's scrollToIndex: FullLog's auto-scroll effect is the only caller.
const scrollToIndex = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-virtual", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-virtual")>()
  return {
    ...actual,
    useVirtualizer: (...args: Parameters<typeof actual.useVirtualizer>) => {
      const instance = actual.useVirtualizer(...args)
      instance.scrollToIndex = scrollToIndex
      return instance
    },
  }
})

let _nextId = 1

function makeLogEntry(
  eventType: PerceivedEvent["event_type"],
  description: string,
  actorId: string | null = null,
  data?: Record<string, unknown>,
): LogEntry {
  return { id: _nextId++, event: { event_type: eventType, description, actor_id: actorId, data } }
}

function makeMoveEntry(actorId: string, distanceFt: number): LogEntry {
  return makeLogEntry("entity_move", `${actorId} moves ${distanceFt} ft`, actorId, {
    distance_ft: distanceFt,
    entity_id: actorId,
  })
}

function appendLog(...entries: LogEntry[]) {
  act(() => {
    useGameStore.setState((s) => ({ log: [...s.log, ...entries] }))
  })
}

/** Put the scroll container `distanceFromBottom` px above its bottom and fire onScroll. */
function scrollContainer(el: HTMLElement, distanceFromBottom: number) {
  Object.defineProperty(el, "scrollHeight", { configurable: true, value: 1000 })
  Object.defineProperty(el, "clientHeight", { configurable: true, value: 200 })
  el.scrollTop = 800 - distanceFromBottom
  fireEvent.scroll(el)
}

// jsdom lays nothing out; give elements a size so the virtualizer renders rows.
const sizeProps = ["offsetHeight", "offsetWidth"] as const
const originalSizes = sizeProps.map((p) => Object.getOwnPropertyDescriptor(HTMLElement.prototype, p))

beforeAll(() => {
  for (const p of sizeProps) {
    Object.defineProperty(HTMLElement.prototype, p, { configurable: true, get: () => 400 })
  }
})

afterAll(() => {
  sizeProps.forEach((p, i) => {
    const original = originalSizes[i]
    if (original) Object.defineProperty(HTMLElement.prototype, p, original)
  })
})

beforeEach(() => {
  _nextId = 1
  scrollToIndex.mockClear()
  useGameStore.setState({ log: [] })
})

describe("EventLog (full) — auto-scroll", () => {
  it("scrolls to the newest entry once per appended entry", () => {
    render(<EventLog />)
    expect(scrollToIndex).not.toHaveBeenCalled()

    appendLog(makeLogEntry("entity_attack", "A attacks B", "a"))
    expect(scrollToIndex).toHaveBeenCalledTimes(1)
    expect(scrollToIndex).toHaveBeenLastCalledWith(0, { align: "end" })

    appendLog(makeLogEntry("entity_attack", "B attacks A", "b"))
    expect(scrollToIndex).toHaveBeenCalledTimes(2)
    expect(scrollToIndex).toHaveBeenLastCalledWith(1, { align: "end" })
  })

  it("does not re-run on re-renders that add no entries", async () => {
    const user = userEvent.setup()
    appendLog(makeMoveEntry("goblin_1", 5), makeMoveEntry("goblin_1", 10))
    const { rerender } = render(<EventLog />)
    expect(scrollToIndex).toHaveBeenCalledTimes(1)

    // Expanding the aggregated move re-renders FullLog (and re-measures) without new entries.
    await user.click(screen.getByTestId("aggregated-move-expand"))
    rerender(<EventLog />)
    // Store updates that leave the log length unchanged re-render too.
    act(() => {
      useGameStore.setState((s) => ({ log: [...s.log] }))
    })

    expect(scrollToIndex).toHaveBeenCalledTimes(1)
  })

  it("stops following new entries after the user scrolls up and resumes at the bottom", () => {
    appendLog(makeLogEntry("entity_attack", "A attacks B", "a"))
    const { container } = render(<EventLog />)
    const scroller = container.firstElementChild as HTMLElement
    expect(scrollToIndex).toHaveBeenCalledTimes(1)

    scrollContainer(scroller, 300)
    appendLog(makeLogEntry("entity_attack", "B attacks A", "b"))
    expect(scrollToIndex).toHaveBeenCalledTimes(1)

    scrollContainer(scroller, 0)
    appendLog(makeLogEntry("entity_attack", "A attacks B again", "a"))
    expect(scrollToIndex).toHaveBeenCalledTimes(2)
    expect(scrollToIndex).toHaveBeenLastCalledWith(2, { align: "end" })
  })
})
