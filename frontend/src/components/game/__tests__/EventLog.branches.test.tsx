import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"
import { useGameStore } from "@/store/gameStore"
import type { LogEntry } from "@/store/slices/logSlice"
import type { AttackRollData, PerceivedEvent } from "@/types/game"
import { EventLog } from "../EventLog"

// EventLog is store-driven: neither rendering nor its local interactions need HTTP.
vi.mock("@/transport/apiClient", () => ({
  api: { master: {}, player: {}, health: vi.fn() },
}))

function entry(id: number, event: PerceivedEvent): LogEntry {
  return { id, event }
}

function setLog(log: LogEntry[]) {
  act(() => useGameStore.setState({ log }))
}

const attackRoll: AttackRollData = {
  natural: 14,
  d20: { sides: 20, result: 14 },
  components: [{ source: "str", value: 3, dice: "" }],
  total: 17,
  advantage: false,
  disadvantage: false,
}

function attackEntry(id: number, weapon: string, hit: boolean): LogEntry {
  return entry(id, {
    event_type: "entity_attack",
    description: `Mira attacks with ${weapon}`,
    actor_id: "mira",
    data: {
      attacker_name: "Mira",
      target_name: "Goblin",
      weapon,
      hit,
      critical: false,
      ac: 15,
      attack_roll: attackRoll,
    },
  })
}

const originalLanguage = i18n.language

beforeEach(async () => {
  await i18n.changeLanguage("en")
  useGameStore.setState({ log: [] })
  // jsdom has no layout. Give the real virtualizer a visible viewport so these
  // tests exercise FullLog's rows rather than only its empty outer container.
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(600)
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(800)
})

afterEach(async () => {
  cleanup()
  vi.restoreAllMocks()
  useGameStore.setState({ log: [] })
  await i18n.changeLanguage(originalLanguage)
})

describe("EventLog — previously uncovered branches", () => {
  it("reaches incoming events from the initial waiting state and restores it when cleared", async () => {
    render(<EventLog />)
    expect(screen.getByText("Waiting for events...")).toBeVisible()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    setLog([
      entry(1, { event_type: "entity_use_item", description: "Mira drinks a potion" }),
      entry(2, { event_type: "action_error", description: "No actions remaining" }),
    ])

    expect(await screen.findByText("Mira drinks a potion")).toBeVisible()
    expect(screen.getByText("No actions remaining")).toBeVisible()
    expect(screen.queryByText("Waiting for events...")).not.toBeInTheDocument()

    setLog([])
    expect(screen.getByText("Waiting for events...")).toBeVisible()
    expect(screen.queryByText("Mira drinks a potion")).not.toBeInTheDocument()
    expect(screen.queryByText("No actions remaining")).not.toBeInTheDocument()
  })

  it("keeps an empty compact log quiet without an expand callback", () => {
    render(<EventLog compact />)

    expect(screen.queryByText("Waiting for events...")).not.toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("calls the supplied expand callback once when clicked", async () => {
    const user = userEvent.setup()
    const onExpand = vi.fn()
    render(<EventLog compact onExpand={onExpand} />)

    await user.click(screen.getByRole("button"))

    expect(onExpand).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders round and named turn headers in full mode and collapses expanded movement details", async () => {
    const user = userEvent.setup()
    setLog([
      entry(1, { event_type: "combat_started", description: "Combat begins" }),
      entry(2, { event_type: "round_start", description: "New round", data: { round_number: 3 } }),
      entry(3, {
        event_type: "entity_move",
        description: "Mira steps past the tree",
        actor_id: "mira",
        actor_name: "Mira",
        data: { distance_ft: 5 },
      }),
      entry(4, {
        event_type: "entity_move",
        description: "Mira reaches the gate",
        actor_id: "mira",
        actor_name: "Mira",
        data: { distance_ft: 10 },
      }),
    ])
    render(<EventLog />)

    expect(await screen.findByText("Round 3")).toBeVisible()
    expect(screen.getByText("Mira", { exact: true })).toBeVisible()
    expect(screen.getByText("Mira moved (15 ft)")).toBeVisible()
    expect(screen.queryByText("New round")).not.toBeInTheDocument()
    expect(screen.queryByText("Mira reaches the gate")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button"))
    expect(screen.getByText("Mira steps past the tree")).toBeVisible()
    expect(screen.getByText("Mira reaches the gate")).toBeVisible()

    await user.click(screen.getByRole("button"))
    expect(screen.queryByText("Mira steps past the tree")).not.toBeInTheDocument()
    expect(screen.queryByText("Mira reaches the gate")).not.toBeInTheDocument()
    expect(screen.getByText("Mira moved (15 ft)")).toBeVisible()
  })

  it.each([
    { mode: "compact", compact: true, hit: true, verdict: "HIT" },
    { mode: "full", compact: false, hit: false, verdict: "MISS" },
  ])("opens the selected attack card and closes/reopens it in $mode mode", async ({ compact, hit, verdict }) => {
    const user = userEvent.setup()
    setLog([attackEntry(1, "Longsword", hit), attackEntry(2, "Shortbow", hit)])
    render(<EventLog compact={compact} />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    await user.click(await screen.findByText("Mira attacks with Longsword"))

    const dialog = await screen.findByRole("dialog", { name: "Longsword Attack" })
    expect(within(dialog).getByText("Mira → Goblin")).toBeVisible()
    expect(within(dialog).getByText(verdict)).toBeVisible()
    expect(within(dialog).getByText("= 17")).toBeVisible()
    expect(within(dialog).getByText("vs AC 15")).toBeVisible()

    await user.click(within(dialog).getByRole("button", { name: "Close" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())

    await user.click(screen.getByText("Mira attacks with Shortbow"))
    expect(await screen.findByRole("dialog", { name: "Shortbow Attack" })).toBeVisible()
    expect(screen.queryByRole("dialog", { name: "Longsword Attack" })).not.toBeInTheDocument()

    await user.keyboard("{Escape}")
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(screen.getByText("Mira attacks with Shortbow")).toBeVisible()
  })

  it("does not open cards for attacks without a valid breakdown or for non-attack events", async () => {
    const user = userEvent.setup()
    const descriptions = ["Legacy attack", "Incomplete attack", "A story about an attack"]
    setLog([
      entry(1, { event_type: "entity_attack", description: descriptions[0] }),
      entry(2, {
        event_type: "entity_attack",
        description: descriptions[1],
        data: { attack_roll: { natural: 14, total: 17 } },
      }),
      entry(3, {
        event_type: "custom",
        description: descriptions[2],
        data: { attack_roll: attackRoll },
      }),
    ])
    render(<EventLog />)

    for (const description of descriptions) {
      const rowText = await screen.findByText(description)
      expect(rowText).toBeVisible()
      await user.click(rowText)
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    }
  })
})
