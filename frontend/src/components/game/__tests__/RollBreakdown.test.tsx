import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import "@/i18n"
import { useGameStore } from "@/store/gameStore"
import { EventLog } from "../EventLog"
import type { PerceivedEvent } from "@/types/game"
import type { LogEntry } from "@/store/slices/logSlice"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _nextId = 1

function makeLogEntry(
  eventType: PerceivedEvent["event_type"],
  description: string,
  actorId?: string | null,
  data?: Record<string, unknown>,
): LogEntry {
  return {
    id: _nextId++,
    event: {
      event_type: eventType,
      description,
      actor_id: actorId ?? null,
      data,
    },
  }
}

function makeAttackEntry(opts?: {
  advantage?: boolean
  disadvantage?: boolean
  hit?: boolean
  critical?: boolean
  withDamage?: boolean
  withReroll?: boolean
}): LogEntry {
  const {
    advantage = false,
    disadvantage = false,
    hit = true,
    critical = false,
    withDamage = true,
    withReroll = false,
  } = opts ?? {}

  const attackRoll: Record<string, unknown> = {
    natural: 14,
    d20: { sides: 20, result: 14 },
    components: [
      { source: "ability", value: 3, dice: "" },
      { source: "proficiency", value: 2, dice: "" },
    ],
    total: 19,
    advantage,
    disadvantage,
  }
  if (advantage || disadvantage) {
    attackRoll.d20_alt = { sides: 20, result: 7 }
  }

  const data: Record<string, unknown> = {
    attacker_id: "fighter_1",
    target_id: "goblin_1",
    weapon: "Longsword",
    hit,
    critical,
    ac: 15,
    attack_roll: attackRoll,
  }

  if (hit && withDamage) {
    const diceDetail = withReroll
      ? [{ sides: 8, result: 5, original: 1 }]
      : [{ sides: 8, result: 6 }]

    data.damage = 8
    data.damage_components = [
      {
        source: "weapon",
        dice: "1d8",
        dice_detail: diceDetail,
        amount: 6,
        type: "slashing",
      },
      {
        source: "ability",
        dice: "",
        dice_detail: [],
        amount: 3,
        type: "slashing",
      },
    ]
  }

  return makeLogEntry(
    "entity_attack",
    "Fighter attacks Goblin with Longsword — 19 vs AC 15, hit! 8 slashing damage",
    "fighter_1",
    data,
  )
}

function setLog(entries: LogEntry[]) {
  useGameStore.setState({ log: entries })
}

beforeEach(() => {
  _nextId = 1
  useGameStore.setState({ log: [] })
})

// ---------------------------------------------------------------------------
// Expandable attacks
// ---------------------------------------------------------------------------

describe("RollBreakdown — expandable attack events", () => {
  it("attack event row has an expand control", () => {
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    expect(screen.getByTestId("attack-expand")).toBeInTheDocument()
  })

  it("clicking toggles expanded state", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    // Initially collapsed — no breakdown visible
    expect(screen.queryByTestId("roll-breakdown")).not.toBeInTheDocument()

    // Click to expand
    await user.click(screen.getByTestId("attack-expand"))
    expect(screen.getByTestId("roll-breakdown")).toBeInTheDocument()

    // Click again to collapse
    await user.click(screen.getByTestId("attack-expand"))
    expect(screen.queryByTestId("roll-breakdown")).not.toBeInTheDocument()
  })

  it("expanded view shows d20 natural value", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    // d20 natural value 14
    expect(within(breakdown).getByText(/14/)).toBeInTheDocument()
  })

  it("expanded view shows modifier components with source labels", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    expect(within(breakdown).getAllByText(/ability/i).length).toBeGreaterThanOrEqual(1)
    expect(within(breakdown).getByText(/proficiency/i)).toBeInTheDocument()
  })

  it("expanded view shows total vs AC and hit/miss", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ hit: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    expect(within(breakdown).getByText(/19/)).toBeInTheDocument()
    expect(within(breakdown).getByText(/AC\s*15/i)).toBeInTheDocument()
    expect(within(breakdown).getByText(/hit/i)).toBeInTheDocument()
  })

  it("expanded view shows damage components with dice faces", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ withDamage: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    // Weapon damage source
    expect(within(breakdown).getByText(/weapon/i)).toBeInTheDocument()
    // Die face [6]
    expect(within(breakdown).getByText(/\[6\]/)).toBeInTheDocument()
  })

  it("shows both d20 values when advantage is present", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ advantage: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    // Advantage line shows kept/dropped values
    expect(within(breakdown).getByText(/kept 14/)).toBeInTheDocument()
    expect(within(breakdown).getByText(/dropped 7/)).toBeInTheDocument()
  })

  it("shows rerolled dice with original value indicator", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ withDamage: true, withReroll: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    // Rerolled die: original (line-through) and arrow → new value, split across elements
    // Use textContent on parent to find the combined "1→5"
    const rerollSpan = within(breakdown).getByText((_content, element) => {
      return element?.classList?.contains("font-mono") === true &&
        element?.textContent?.includes("→") === true &&
        element?.textContent?.includes("1") === true &&
        element?.textContent?.includes("5") === true
    })
    expect(rerollSpan).toBeInTheDocument()
  })

  it("graceful degradation — legacy events without dice_detail show basic info", async () => {
    const user = userEvent.setup()
    // Event with attack_roll but no damage_components (legacy)
    const entry = makeLogEntry(
      "entity_attack",
      "Fighter attacks Goblin — hit! 8 damage",
      "fighter_1",
      {
        attacker_id: "fighter_1",
        target_id: "goblin_1",
        weapon: "Longsword",
        hit: true,
        critical: false,
        ac: 15,
        attack_roll: {
          natural: 14,
          d20: { sides: 20, result: 14 },
          components: [],
          total: 19,
          advantage: false,
          disadvantage: false,
        },
        damage: 8,
        // No damage_components — legacy
      },
    )
    setLog([entry])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-expand"))
    const breakdown = screen.getByTestId("roll-breakdown")
    // Should still show the d20 and total
    expect(within(breakdown).getByText(/14/)).toBeInTheDocument()
    expect(within(breakdown).getByText(/19/)).toBeInTheDocument()
  })

  it("non-attack events are NOT expandable", () => {
    setLog([
      makeLogEntry("entity_say", "Hello there", "npc_1"),
      makeLogEntry("entity_dodge", "Fighter dodges", "fighter_1"),
    ])
    render(<EventLog compact onExpand={vi.fn()} />)

    expect(screen.queryByTestId("attack-expand")).not.toBeInTheDocument()
  })

  it("events without attack_roll data are NOT expandable", () => {
    // entity_attack event but with no structured data
    setLog([makeLogEntry("entity_attack", "You attack goblin", "player_1")])
    render(<EventLog compact onExpand={vi.fn()} />)

    // No expand button — no data to show
    expect(screen.queryByTestId("attack-expand")).not.toBeInTheDocument()
  })
})
