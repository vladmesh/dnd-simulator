import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import "@/i18n"
import { AttackCardModal } from "../AttackCardModal"
import type { AttackCardData } from "../AttackCardModal"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCardData(overrides?: Partial<AttackCardData>): AttackCardData {
  return {
    attackerName: "Fighter",
    targetName: "Goblin",
    weapon: "Longsword",
    hit: true,
    critical: false,
    ac: 15,
    attackRoll: {
      natural: 14,
      d20: { sides: 20, result: 14 },
      components: [
        { source: "str", value: 3, dice: "" },
        { source: "Proficiency", value: 2, dice: "" },
      ],
      total: 19,
      advantage: false,
      disadvantage: false,
    },
    totalDamage: 9,
    damageComponents: [
      {
        source: "weapon",
        dice: "1d8",
        dice_detail: [{ sides: 8, result: 6 }],
        amount: 6,
        type: "slashing",
      },
      {
        source: "str",
        dice: "",
        dice_detail: [],
        amount: 3,
        type: "slashing",
      },
    ],
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AttackCardModal", () => {
  it("renders attacker, target, and weapon name", () => {
    render(<AttackCardModal data={makeCardData()} open onOpenChange={vi.fn()} />)
    expect(screen.getByText(/Fighter/)).toBeInTheDocument()
    expect(screen.getByText(/Goblin/)).toBeInTheDocument()
    expect(screen.getByText(/Longsword/i)).toBeInTheDocument()
  })

  it("shows HIT verdict badge when hit", () => {
    render(<AttackCardModal data={makeCardData({ hit: true })} open onOpenChange={vi.fn()} />)
    expect(screen.getByTestId("verdict-badge")).toHaveTextContent("HIT")
  })

  it("shows MISS verdict badge when miss", () => {
    render(
      <AttackCardModal
        data={makeCardData({ hit: false, totalDamage: undefined, damageComponents: undefined })}
        open
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.getByTestId("verdict-badge")).toHaveTextContent("MISS")
  })

  it("shows CRIT verdict badge when critical", () => {
    render(
      <AttackCardModal data={makeCardData({ critical: true })} open onOpenChange={vi.fn()} />,
    )
    expect(screen.getByTestId("verdict-badge")).toHaveTextContent("CRIT")
  })

  it("renders d20 as a visual die, not text", () => {
    render(<AttackCardModal data={makeCardData()} open onOpenChange={vi.fn()} />)
    expect(screen.getByTestId("die-d20")).toBeInTheDocument()
    expect(screen.getByTestId("die-d20")).toHaveTextContent("14")
  })

  it("shows each modifier on its own line with source and value", () => {
    render(<AttackCardModal data={makeCardData()} open onOpenChange={vi.fn()} />)
    const section = screen.getByTestId("attack-roll-section")
    expect(within(section).getByText(/\+3/)).toBeInTheDocument()
    expect(within(section).getByText(/STR/)).toBeInTheDocument()
    expect(within(section).getByText(/\+2/)).toBeInTheDocument()
    expect(within(section).getByText(/Proficiency/)).toBeInTheDocument()
  })

  it("shows total vs AC result", () => {
    render(<AttackCardModal data={makeCardData()} open onOpenChange={vi.fn()} />)
    const section = screen.getByTestId("attack-roll-section")
    expect(within(section).getByText(/19/)).toBeInTheDocument()
    expect(within(section).getByText(/AC 15/)).toBeInTheDocument()
  })

  it("shows damage dice as visual die faces", () => {
    render(<AttackCardModal data={makeCardData()} open onOpenChange={vi.fn()} />)
    const section = screen.getByTestId("damage-section")
    // d8 visual die with result 6
    expect(within(section).getByTestId("die-d8")).toHaveTextContent("6")
  })

  it("shows total damage prominently", () => {
    render(<AttackCardModal data={makeCardData()} open onOpenChange={vi.fn()} />)
    const total = screen.getByTestId("total-damage")
    expect(total).toHaveTextContent("9")
  })

  it("shows rolled damage with overkill indicator when clamped", () => {
    render(
      <AttackCardModal
        data={makeCardData({ totalDamage: 5, rolledDamage: 9 })}
        open
        onOpenChange={vi.fn()}
      />,
    )
    const total = screen.getByTestId("total-damage")
    // Shows rolled amount as the main number
    expect(total).toHaveTextContent("9")
    // Shows dealt amount in parentheses
    expect(total).toHaveTextContent("5")
  })

  it("does not show damage section on miss", () => {
    render(
      <AttackCardModal
        data={makeCardData({ hit: false, totalDamage: undefined, damageComponents: undefined })}
        open
        onOpenChange={vi.fn()}
      />,
    )
    expect(screen.queryByTestId("damage-section")).not.toBeInTheDocument()
  })

  it("shows two d20s with advantage — kept and dropped", () => {
    render(
      <AttackCardModal
        data={makeCardData({
          attackRoll: {
            natural: 14,
            d20: { sides: 20, result: 14 },
            d20_alt: { sides: 20, result: 7 },
            components: [],
            total: 14,
            advantage: true,
            disadvantage: false,
          },
        })}
        open
        onOpenChange={vi.fn()}
      />,
    )
    // Two d20 dice should be visible
    const d20s = screen.getAllByTestId("die-d20")
    expect(d20s.length).toBe(2)
    // One should be dropped (dimmed)
    const droppedDie = d20s.find((el) => el.className.match(/opacity/))
    expect(droppedDie).toBeDefined()
  })

  it("shows ring on d20 when critical", () => {
    render(
      <AttackCardModal data={makeCardData({ critical: true })} open onOpenChange={vi.fn()} />,
    )
    const d20 = screen.getByTestId("die-d20")
    expect(d20.className).toMatch(/sky/)
  })

  it("shows reroll visually in damage dice", () => {
    render(
      <AttackCardModal
        data={makeCardData({
          damageComponents: [
            {
              source: "weapon",
              dice: "1d8",
              dice_detail: [{ sides: 8, result: 5, original: 1 }],
              amount: 5,
              type: "slashing",
            },
          ],
        })}
        open
        onOpenChange={vi.fn()}
      />,
    )
    // Should show original die dimmed
    expect(screen.getByTestId("die-original")).toHaveTextContent("1")
    // Arrow
    expect(screen.getByText("→")).toBeInTheDocument()
    // New die
    expect(screen.getByTestId("die-d8")).toHaveTextContent("5")
  })

  it("calls onOpenChange(false) when close button is clicked", async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(<AttackCardModal data={makeCardData()} open onOpenChange={onOpenChange} />)

    const closeBtn = screen.getByRole("button", { name: /close/i })
    await user.click(closeBtn)
    expect(onOpenChange).toHaveBeenCalled()
    expect(onOpenChange.mock.calls[0][0]).toBe(false)
  })
})
