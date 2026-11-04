import { useState, type ComponentProps } from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"
import { ActionButton } from "../ActionButton"
import { MAX_SPEECH_LENGTH } from "../../speechLimit"
import type { ActionInfo, TurnBudget } from "@/types/game"

// Actions are dispatched through sendAction, not REST. Keep this boundary mocked.
vi.mock("@/transport/apiClient", () => ({ api: {} }))

type Props = ComponentProps<typeof ActionButton>

const fullBudget: TurnBudget = {
  actions: 1,
  bonus_actions: 1,
  movement_remaining: 30,
  reaction: 1,
}

const costAction: ActionInfo = {
  name: "disengage",
  description: "Leave melee safely",
  params: [],
  cost_type: "action",
  cost_options: [
    { cost_type: "action", source: "default" },
    { cost_type: "bonus_action", source: "cunning_action" },
  ],
}

function makeAction(overrides: Partial<ActionInfo>): ActionInfo {
  return { name: "inspect", description: "Inspect surroundings", params: [], ...overrides }
}

function Harness(props: Partial<Props>) {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  return (
    <ActionButton
      action={costAction}
      nearby={[]}
      disabled={false}
      budget={fullBudget}
      sendAction={vi.fn()}
      t={(key, opts) => i18n.t(key, opts)}
      {...props}
      openDropdown={openDropdown}
      setOpenDropdown={setOpenDropdown}
    />
  )
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
})

describe("ActionButton — uncovered cost choices", () => {
  it("starts closed, blocks interaction while disabled, and toggles once enabled without a budget", () => {
    const sendAction = vi.fn()
    const { rerender } = render(<Harness disabled budget={undefined} sendAction={sendAction} />)

    const trigger = screen.getByRole("button", { name: "Disengage" })
    expect(trigger).toBeDisabled()
    fireEvent.click(trigger)
    expect(screen.queryByRole("button", { name: "Action" })).not.toBeInTheDocument()

    rerender(<Harness budget={undefined} sendAction={sendAction} />)
    expect(trigger).toBeEnabled()
    fireEvent.click(trigger)
    expect(screen.getByRole("button", { name: "Action" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Bonus Action(cunning action)" })).toBeEnabled()
    fireEvent.click(trigger)
    expect(screen.queryByRole("button", { name: "Action" })).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()
  })

  it("sends the default cost without a cost_mode and closes the choices", () => {
    const sendAction = vi.fn()
    render(<Harness sendAction={sendAction} />)

    fireEvent.click(screen.getByRole("button", { name: "Disengage" }))
    fireEvent.click(screen.getByRole("button", { name: "Action" }))

    expect(sendAction).toHaveBeenCalledExactlyOnceWith("disengage", {})
    expect(screen.queryByRole("button", { name: "Action" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Bonus Action(cunning action)" })).not.toBeInTheDocument()
  })

  it("sends the alternate cost_mode and closes the choices", () => {
    const sendAction = vi.fn()
    render(<Harness sendAction={sendAction} />)

    fireEvent.click(screen.getByRole("button", { name: "Disengage" }))
    fireEvent.click(screen.getByRole("button", { name: "Bonus Action(cunning action)" }))

    expect(sendAction).toHaveBeenCalledExactlyOnceWith("disengage", { cost_mode: "bonus_action" })
    expect(screen.queryByRole("button", { name: "Bonus Action(cunning action)" })).not.toBeInTheDocument()
  })

  it("blocks a depleted default cost but still allows the available alternative", () => {
    const sendAction = vi.fn()
    render(<Harness budget={{ ...fullBudget, actions: 0 }} sendAction={sendAction} />)

    fireEvent.click(screen.getByRole("button", { name: "Disengage" }))
    const defaultCost = screen.getByRole("button", { name: "Action" })
    expect(defaultCost).toBeDisabled()
    fireEvent.click(defaultCost)
    expect(sendAction).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Bonus Action(cunning action)" })).toBeEnabled()
    fireEvent.click(screen.getByRole("button", { name: "Bonus Action(cunning action)" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("disengage", { cost_mode: "bonus_action" })
  })

  it("keeps depleted choices inspectable but prevents dispatch when all costs are exhausted", () => {
    const sendAction = vi.fn()
    render(<Harness budget={{ ...fullBudget, actions: 0, bonus_actions: 0 }} sendAction={sendAction} />)

    const trigger = screen.getByRole("button", { name: "Disengage" })
    // Depletion intentionally disables the options, not the menu trigger.
    expect(trigger).toBeEnabled()
    fireEvent.click(trigger)
    for (const name of ["Action", "Bonus Action(cunning action)"]) {
      const option = screen.getByRole("button", { name })
      expect(option).toBeDisabled()
      fireEvent.click(option)
    }
    expect(sendAction).not.toHaveBeenCalled()
  })

  // BUG: i18next strips the namespace from missing keys, bypassing the readable cost-label fallback.
  it.fails("uses readable fallback cost labels when a translation and default cost type are absent", () => {
    const sendAction = vi.fn()
    render(
      <Harness
        action={makeAction({
          cost_options: [
            { cost_type: "special_cost", source: "custom_feature" },
            { cost_type: "free", source: "default" },
          ],
        })}
        sendAction={sendAction}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }))
    expect(screen.getByRole("button", { name: "Free" })).toBeEnabled()
    fireEvent.click(screen.getByRole("button", { name: "special cost(custom feature)" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("inspect", { cost_mode: "special_cost" })
  })
})

describe("ActionButton — uncovered routing and validation", () => {
  it("does not offer a cost menu for empty or single-entry cost options", () => {
    const sendAction = vi.fn()
    const action = makeAction({ cost_options: [] })
    const { rerender } = render(<Harness action={action} sendAction={sendAction} />)

    expect(screen.getAllByRole("button")).toHaveLength(1)
    rerender(
      <Harness
        action={{ ...action, cost_options: [{ cost_type: "action", source: "default" }] }}
        sendAction={sendAction}
      />,
    )
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("inspect")
    expect(screen.getAllByRole("button")).toHaveLength(1)
  })

  it("uses hostile targeting for legacy target_id actions without target_mode", () => {
    const sendAction = vi.fn()
    render(
      <Harness
        action={makeAction({ params: [{ name: "target_id", type: "string", required: true }] })}
        nearby={[
          { id: "goblin", description: "Goblin", is_hostile: true },
          { id: "orc", description: "Orc", is_hostile: true },
          { id: "guard", description: "Friendly Guard", is_hostile: false },
        ]}
        sendAction={sendAction}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }))
    expect(screen.getByRole("menu", { name: "Inspect surroundings" })).toBeVisible()
    expect(screen.queryByRole("menuitem", { name: /Friendly Guard/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("menuitem", { name: "Orc" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("inspect", { target_id: "orc" })
  })

  it("can target self with an ally action even when nobody is nearby", () => {
    const sendAction = vi.fn()
    render(
      <Harness
        action={makeAction({ name: "bless", target_mode: "single", target_scope: "ally" })}
        selfId="hero"
        nearby={[]}
        sendAction={sendAction}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Bless" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("bless", { target_id: "hero" })
  })

  it("routes a direction parameter to toward/away choices and can close the menu", () => {
    const sendAction = vi.fn()
    render(
      <Harness
        action={makeAction({ name: "move", params: [{ name: "direction", type: "string", required: false }] })}
        nearby={[{ id: "ogre", description: "Ogre", is_hostile: true }]}
        sendAction={sendAction}
      />,
    )

    const trigger = screen.getByRole("button", { name: "Move" })
    fireEvent.click(trigger)
    fireEvent.click(screen.getByRole("button", { name: "Toward Ogre" }))
    expect(sendAction).toHaveBeenNthCalledWith(1, "move", { toward: "ogre" })
    fireEvent.click(screen.getByRole("button", { name: "Away from Ogre" }))
    expect(sendAction).toHaveBeenNthCalledWith(2, "move", { away_from: "ogre" })
    expect(sendAction).toHaveBeenCalledTimes(2)
    fireEvent.click(trigger)
    expect(screen.queryByRole("button", { name: "Toward Ogre" })).not.toBeInTheDocument()
  })

  it("falls back to a simple, disableable button for target/direction params with no nearby entities", () => {
    const sendAction = vi.fn()
    const action = makeAction({
      target_mode: "single",
      params: ["target_id", "toward", "direction"].map((name) => ({ name, type: "string", required: false })),
    })
    const { rerender } = render(<Harness action={action} disabled sendAction={sendAction} />)

    const button = screen.getByRole("button", { name: "Inspect" })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(sendAction).not.toHaveBeenCalled()
    rerender(<Harness action={action} sendAction={sendAction} />)
    fireEvent.click(button)
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("inspect")
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("shows a speech length error, blocks sending, and recovers after the draft is shortened", () => {
    const sendAction = vi.fn()
    render(<Harness action={makeAction({ name: "say" })} sendAction={sendAction} />)

    fireEvent.click(screen.getByRole("button", { name: "Say" }))
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "x".repeat(MAX_SPEECH_LENGTH + 1) } })
    expect(screen.getByRole("alert")).toHaveTextContent(
      `Too long: ${MAX_SPEECH_LENGTH + 1} of ${MAX_SPEECH_LENGTH} characters. Shorten it to send.`,
    )
    expect(input).toBeInvalid()
    expect(screen.getByRole("button", { name: "↵" })).toBeDisabled()
    fireEvent.keyDown(input, { key: "Enter" })
    expect(sendAction).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: "  Short enough  " } })
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(input).toBeValid()
    const submit = screen.getByRole("button", { name: "↵" })
    expect(submit).toBeEnabled()
    fireEvent.click(submit)
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("say", { text: "Short enough" })
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  })
})
