import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { DieVisual } from "../DiceVisual"

describe("DieVisual", () => {
  it("renders a d20 at large size with the result number", () => {
    render(<DieVisual sides={20} result={14} />)
    const die = screen.getByTestId("die-d20")
    expect(die).toBeInTheDocument()
    expect(die).toHaveTextContent("14")
    // d20 should be large (40x40)
    expect(die.className).toMatch(/w-10/)
    expect(die.className).toMatch(/h-10/)
  })

  it("renders a d6 at medium size", () => {
    render(<DieVisual sides={6} result={4} />)
    const die = screen.getByTestId("die-d6")
    expect(die).toBeInTheDocument()
    expect(die).toHaveTextContent("4")
    expect(die.className).toMatch(/w-7/)
    expect(die.className).toMatch(/h-7/)
  })

  it("renders d8, d10, d12 at medium size", () => {
    const { unmount } = render(<DieVisual sides={8} result={5} />)
    expect(screen.getByTestId("die-d8")).toBeInTheDocument()
    unmount()

    const { unmount: u2 } = render(<DieVisual sides={10} result={7} />)
    expect(screen.getByTestId("die-d10")).toBeInTheDocument()
    u2()

    render(<DieVisual sides={12} result={11} />)
    expect(screen.getByTestId("die-d12")).toBeInTheDocument()
  })

  it("shows reroll: original die dimmed + strikethrough, arrow, new die", () => {
    render(<DieVisual sides={8} result={5} original={1} />)
    const original = screen.getByTestId("die-original")
    expect(original).toHaveTextContent("1")
    expect(original.className).toMatch(/opacity/)
    expect(original.className).toMatch(/line-through/)

    expect(screen.getByText("→")).toBeInTheDocument()

    const newDie = screen.getByTestId("die-d8")
    expect(newDie).toHaveTextContent("5")
  })

  it("shows ring on d20 when critical", () => {
    render(<DieVisual sides={20} result={20} critical />)
    const die = screen.getByTestId("die-d20")
    expect(die.className).toMatch(/sky/)
  })

  it("shows dimmed state when dropped (advantage/disadvantage)", () => {
    render(<DieVisual sides={20} result={7} dropped />)
    const die = screen.getByTestId("die-d20")
    expect(die.className).toMatch(/opacity/)
  })
})
