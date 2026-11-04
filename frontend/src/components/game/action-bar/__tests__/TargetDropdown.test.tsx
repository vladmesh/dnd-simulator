import { useState, type ComponentProps } from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"

// This component delegates actions to its parent, rather than calling REST.
vi.mock("@/transport/apiClient", () => ({
  api: { player: { getStatus: vi.fn(), levelUp: vi.fn() } },
}))

// The real amount picker reads the store; keep its transport disconnected.
vi.mock("@/transport/wsClient", () => ({
  wsClient: {
    send: vi.fn(),
    onStatus: vi.fn(() => vi.fn()),
    onMessage: vi.fn(() => vi.fn()),
    getStatus: vi.fn(() => "disconnected"),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

import { TargetDropdown } from "../TargetDropdown"
import { useGameStore } from "@/store/gameStore"
import type { ResourcePoolInfo } from "@/types/game"

type Props = ComponentProps<typeof TargetDropdown>

const nearby: Props["nearby"] = [
  { id: "goblin-1", description: "Goblin", distance_ft: 5, is_hostile: true },
  { id: "goblin-2", description: "Goblin archer", distance_ft: 20, is_hostile: true },
  { id: "friend", name: "Mira", is_hostile: false },
]

const spellSlots: ResourcePoolInfo[] = [
  { id: "spell_slot_1", current_uses: 0, max_uses: 2 },
  { id: "spell_slot_2", current_uses: 1, max_uses: 1 },
]
const layPool: ResourcePoolInfo = { id: "lay_on_hands", current_uses: 8, max_uses: 10 }

function renderDropdown(overrides: Partial<Props> = {}) {
  const sendAction = vi.fn<Props["sendAction"]>()

  // Exercise the same controlled-dropdown contract as ActionBar.
  function Harness() {
    const [openDropdown, setOpenDropdown] = useState<string | null>(null)
    return (
      <TargetDropdown
        name="attack"
        description="Choose a target"
        nearby={nearby}
        scope="hostile"
        disabled={false}
        depleted={false}
        costClass=""
        {...overrides}
        openDropdown={openDropdown}
        setOpenDropdown={setOpenDropdown}
        sendAction={sendAction}
        t={(key, opts) => i18n.t(key, opts)}
      />
    )
  }

  return { ...render(<Harness />), sendAction }
}

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage("en")
  useGameStore.setState({ awareness: undefined, player: null })
})

describe("TargetDropdown — target selection", () => {
  it("starts closed, toggles a talk menu, and sends the selected perceived target", () => {
    const { sendAction } = renderDropdown({
      name: "talk",
      scope: "any",
      selfId: "hero",
      nearby: [
        { id: "stranger", description: "A hooded stranger", name: "Hidden name", distance_ft: 0 },
        { id: "friend", name: "Mira" },
        { id: "unseen" },
      ],
    })
    const trigger = screen.getByRole("button", { name: "Talk" })
    expect(trigger).toBeEnabled()
    expect(trigger).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()

    fireEvent.click(trigger)
    expect(screen.getByRole("menu", { name: "Choose a target" })).toBeVisible()
    expect(screen.getByRole("menuitem", { name: "Self" })).toBeVisible()
    expect(screen.getByRole("menuitem", { name: /Talk to A hooded stranger\s*\(0ft\)/ })).toBeVisible()
    expect(screen.getByRole("menuitem", { name: "Talk to Mira" })).toBeVisible()
    expect(screen.getByRole("menuitem", { name: "Talk to someone" })).toBeVisible()
    expect(screen.queryByText(/Hidden name|^stranger$|unseen/)).not.toBeInTheDocument()

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()

    fireEvent.click(trigger)
    fireEvent.click(screen.getByRole("menuitem", { name: "Talk to Mira" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("talk", { target_id: "friend" })
  })

  it("does not allow a disabled, depleted action to open or send", () => {
    const { sendAction } = renderDropdown({ disabled: true, depleted: true, costType: "action" })
    const trigger = screen.getByRole("button", { name: "Attack" })
    expect(trigger).toBeDisabled()
    fireEvent.click(trigger)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()
  })

  it("keeps an empty target list inert without inventing a target", () => {
    const { sendAction } = renderDropdown({ nearby: [] })
    const trigger = screen.getByRole("button", { name: "Attack" })
    expect(trigger).not.toHaveAttribute("aria-haspopup")
    fireEvent.click(trigger)
    fireEvent.click(trigger)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()
  })
})

describe("TargetDropdown — smite follow-up", () => {
  it.each([
    { label: "a normal attack", choice: /^Attack Goblin archer$/, params: { target_id: "goblin-2" } },
    {
      label: "a level-two smite",
      choice: /^Attack Goblin archer \+ Smite \(slot 2\)\s*\(1\/1\)$/,
      params: { target_id: "goblin-2", smite_slot_level: 2 },
    },
  ])("sends $label and closes the follow-up", ({ choice, params }) => {
    const { sendAction } = renderDropdown({ spellSlots })
    fireEvent.click(screen.getByRole("button", { name: "Attack" }))
    expect(screen.queryByRole("menuitem", { name: /Mira/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("menuitem", { name: /Attack Goblin archer\s*\(20ft\)/ }))
    expect(sendAction).not.toHaveBeenCalled()
    expect(screen.getByRole("menu", { name: "Attack Goblin archer" })).toBeVisible()

    const depleted = screen.getByRole("menuitem", { name: /Attack Goblin archer \+ Smite \(slot 1\)\s*\(0\/2\)/ })
    expect(depleted).toBeDisabled()
    fireEvent.click(depleted)
    expect(sendAction).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("menuitem", { name: choice }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("attack", params)
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Attack" })).toHaveAttribute("aria-expanded", "false")
  })

  it.each(["Cancel", "Attack"])("cancels smite via %s without retaining the previous target", (cancel) => {
    const { sendAction } = renderDropdown({ spellSlots })
    fireEvent.click(screen.getByRole("button", { name: "Attack" }))
    fireEvent.click(screen.getByRole("menuitem", { name: /Attack Goblin\s*\(5ft\)/ }))
    fireEvent.click(screen.getByRole(cancel === "Cancel" ? "menuitem" : "button", { name: cancel }))
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Attack" }))
    fireEvent.click(screen.getByRole("menuitem", { name: /Attack Goblin archer\s*\(20ft\)/ }))
    expect(screen.getByRole("menu", { name: "Attack Goblin archer" })).toBeVisible()
    expect(screen.queryByRole("menuitem", { name: "Attack Goblin" })).not.toBeInTheDocument()
  })
})

describe("TargetDropdown — Lay on Hands follow-up", () => {
  it("offers self and allies, then confirms an amount without treating spell slots as smite", () => {
    const { sendAction } = renderDropdown({
      name: "lay_on_hands",
      scope: "ally",
      selfId: "hero",
      spellSlots: [...spellSlots, layPool],
    })
    fireEvent.click(screen.getByRole("button", { name: "Lay on Hands" }))
    expect(screen.getAllByRole("menuitem")).toHaveLength(2)
    expect(screen.getByRole("menuitem", { name: "Mira" })).toBeVisible()
    expect(screen.queryByRole("menuitem", { name: /Goblin/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("menuitem", { name: "Self" }))
    expect(screen.getByText("Pool: 8/10 HP")).toBeVisible()
    expect(sendAction).not.toHaveBeenCalled()

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "4" } })
    fireEvent.click(screen.getByRole("button", { name: "Heal 4 HP" }))
    expect(sendAction).toHaveBeenCalledExactlyOnceWith("lay_on_hands", { target_id: "hero", amount: 4 })
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Lay on Hands" })).toHaveAttribute("aria-expanded", "false")
  })

  it.each(["Cancel", "Lay on Hands"])("cancels the amount picker via %s and resets its amount", (cancel) => {
    const { sendAction } = renderDropdown({
      name: "lay_on_hands",
      scope: "ally",
      nearby: [{ id: "friend", description: "Mira" }],
      spellSlots: [layPool],
    })
    fireEvent.click(screen.getByRole("button", { name: "Lay on Hands" }))
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "7" } })
    fireEvent.click(screen.getByRole("button", { name: cancel }))
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Lay on Hands" }))
    expect(screen.getByRole("spinbutton")).toHaveValue(1)
    expect(screen.getByRole("button", { name: "Heal 1 HP" })).toBeVisible()
  })

  it("does not submit a healing action when its resource pool is missing", () => {
    const { sendAction } = renderDropdown({
      name: "lay_on_hands",
      scope: "ally",
      nearby: [{ id: "friend", name: "Mira" }],
      spellSlots: [],
    })
    fireEvent.click(screen.getByRole("button", { name: "Lay on Hands" }))
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument()
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(sendAction).not.toHaveBeenCalled()
  })
})
