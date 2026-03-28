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
    attacker_name: "Fighter",
    target_id: "goblin_1",
    target_name: "Goblin",
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
// Attack card modal — click to open
// ---------------------------------------------------------------------------

describe("Attack card modal — clickable attack events", () => {
  it("attack event row is clickable (has cursor-pointer)", () => {
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    const row = screen.getByTestId("attack-row")
    expect(row.className).toMatch(/cursor-pointer/)
  })

  it("clicking attack row opens modal with attack details", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-row"))

    // Modal should show d20 visual die
    expect(screen.getByTestId("die-d20")).toBeInTheDocument()
    expect(screen.getByTestId("die-d20")).toHaveTextContent("14")
  })

  it("modal shows modifier components with source labels", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry()])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-row"))

    const section = screen.getByTestId("attack-roll-section")
    expect(within(section).getAllByText(/ability/i).length).toBeGreaterThanOrEqual(1)
    expect(within(section).getByText(/proficiency/i)).toBeInTheDocument()
  })

  it("modal shows total vs AC and verdict", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ hit: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-row"))

    const section = screen.getByTestId("attack-roll-section")
    expect(within(section).getByText(/19/)).toBeInTheDocument()
    expect(within(section).getByText(/AC 15/)).toBeInTheDocument()
    expect(screen.getByTestId("verdict-badge")).toHaveTextContent("HIT")
  })

  it("modal shows damage dice as visual die faces", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ withDamage: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-row"))

    const section = screen.getByTestId("damage-section")
    expect(within(section).getByText(/weapon/i)).toBeInTheDocument()
    expect(within(section).getByTestId("die-d8")).toHaveTextContent("6")
  })

  it("shows two d20s when advantage is present", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ advantage: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-row"))

    const d20s = screen.getAllByTestId("die-d20")
    expect(d20s.length).toBe(2)
    // One should be dropped (dimmed)
    const droppedDie = d20s.find((el) => el.className.match(/opacity/))
    expect(droppedDie).toBeDefined()
  })

  it("shows rerolled dice with original value indicator", async () => {
    const user = userEvent.setup()
    setLog([makeAttackEntry({ withDamage: true, withReroll: true })])
    render(<EventLog compact onExpand={vi.fn()} />)

    await user.click(screen.getByTestId("attack-row"))

    // Rerolled die: original die dimmed
    expect(screen.getByTestId("die-original")).toHaveTextContent("1")
    expect(screen.getByText("→")).toBeInTheDocument()
    expect(screen.getByTestId("die-d8")).toHaveTextContent("5")
  })

  it("non-attack events are NOT clickable", () => {
    setLog([
      makeLogEntry("entity_say", "Hello there", "npc_1"),
      makeLogEntry("entity_dodge", "Fighter dodges", "fighter_1"),
    ])
    render(<EventLog compact onExpand={vi.fn()} />)

    expect(screen.queryByTestId("attack-row")).not.toBeInTheDocument()
  })

  it("events without attack_roll data are NOT clickable", () => {
    setLog([makeLogEntry("entity_attack", "You attack goblin", "player_1")])
    render(<EventLog compact onExpand={vi.fn()} />)

    expect(screen.queryByTestId("attack-row")).not.toBeInTheDocument()
  })
})
