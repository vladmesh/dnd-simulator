import { render, screen, fireEvent } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"

// This picker only invokes callbacks; no REST request should be needed.
vi.mock("@/transport/apiClient", () => ({ api: { player: {} } }))

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

import { useGameStore } from "@/store/gameStore"
import type { CombatAwareness, PeacefulAwareness, PlayerStatus } from "@/types/game"
import { LayOnHandsAmountPicker, type LayOnHandsAmountPickerProps } from "../LayOnHandsAmountPicker"

const player: PlayerStatus = {
  player_id: "hero",
  name: "Hero",
  race: "human",
  char_class: "paladin",
  level: 2,
  experience: 300,
  level_up_available: false,
  xp_to_next_level: 600,
  alignment: "lawful_good",
  hp: 0,
  max_hp: 20,
  ac: 16,
  gold: 10,
  location_id: "town",
  ability_scores: { str: 16, dex: 10, con: 14, int: 8, wis: 12, cha: 14 },
}

const combat: CombatAwareness = {
  self_hp: 17,
  self_max_hp: 20,
  self_ac: 16,
  self_speed: 30,
  self_weapon: "Sword",
  self_weapon_damage: "1d8",
  nearby: [],
  round_number: 1,
}

const peaceful: PeacefulAwareness = {
  hour: 12,
  day: 1,
  month: 1,
  year: 1,
  weather: {},
  location_name: "Town",
  region_name: "Valley",
  nearby: [],
}

function renderPicker(overrides: Partial<LayOnHandsAmountPickerProps> = {}) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <LayOnHandsAmountPicker
      name="lay_on_hands"
      description="Restore hit points"
      costType="action"
      costClass=""
      dataAttrs={{}}
      disabled={false}
      pool={{ id: "lay_on_hands", current_uses: 8, max_uses: 10 }}
      targetId="hero"
      selfId="hero"
      onConfirm={onConfirm}
      onCancel={onCancel}
      t={(key, opts) => i18n.t(key, opts)}
      {...overrides}
    />,
  )
  return { onConfirm, onCancel }
}

beforeEach(async () => {
  vi.clearAllMocks()
  useGameStore.setState({ awareness: undefined, player: null })
  await i18n.changeLanguage("en")
})

describe("LayOnHandsAmountPicker — amount controls", () => {
  it("renders immediately with the pool cap when self HP is unknown", () => {
    const { onConfirm } = renderPicker()

    expect(screen.getByText("Pool: 8/10 HP")).toBeVisible()
    expect(screen.getByRole("slider")).toHaveValue("1")
    expect(screen.getByRole("slider")).toHaveAttribute("max", "8")
    expect(screen.getByRole("spinbutton")).toHaveValue(1)
    expect(screen.getByRole("button", { name: "Heal 1 HP" })).toBeEnabled()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it("uses combat HP rather than stale player HP to cap self healing", () => {
    useGameStore.setState({ awareness: combat, player })
    const { onConfirm } = renderPicker()

    expect(screen.getByText("Pool: 3/10 HP")).toBeVisible()
    expect(screen.getByRole("slider")).toHaveAttribute("max", "3")
    const input = screen.getByRole("spinbutton")
    fireEvent.change(input, { target: { value: "8" } })
    fireEvent.blur(input)
    expect(input).toHaveValue(3)
    fireEvent.click(screen.getByRole("button", { name: "Heal 3 HP" }))
    expect(onConfirm).toHaveBeenCalledExactlyOnceWith(3)
  })

  it.each([
    { label: "peaceful awareness", awareness: peaceful, hp: 16, cap: 4 },
    { label: "no awareness and zero HP", awareness: undefined, hp: 0, cap: 8 },
  ])("falls back to player HP with $label, bounded by the pool", ({ awareness, hp, cap }) => {
    useGameStore.setState({ awareness, player: { ...player, hp } })
    const { onConfirm } = renderPicker()

    expect(screen.getByText(`Pool: ${cap}/10 HP`)).toBeVisible()
    expect(screen.getByRole("spinbutton")).toHaveAttribute("max", String(cap))
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "20" } })
    fireEvent.click(screen.getByRole("button", { name: `Heal ${cap} HP` }))
    expect(onConfirm).toHaveBeenCalledExactlyOnceWith(cap)
  })

  it("allows the slider to spend more than the caster's missing HP on an ally", () => {
    useGameStore.setState({ awareness: combat })
    const { onConfirm } = renderPicker({ targetId: "ally" })

    expect(screen.getByText("Pool: 8/10 HP")).toBeVisible()
    fireEvent.change(screen.getByRole("slider"), { target: { value: "6" } })
    expect(screen.getByRole("spinbutton")).toHaveValue(6)
    fireEvent.click(screen.getByRole("button", { name: "Heal 6 HP" }))
    expect(onConfirm).toHaveBeenCalledExactlyOnceWith(6)
  })

  it("normalizes out-of-range and fractional number entries on blur", () => {
    const { onConfirm } = renderPicker()
    const input = screen.getByRole("spinbutton")

    for (const [value, expected] of [["-2", 1], ["25", 8], ["3.9", 3]] as const) {
      fireEvent.change(input, { target: { value } })
      fireEvent.blur(input)
      expect(input).toHaveValue(expected)
      expect(screen.getByRole("slider")).toHaveValue(String(expected))
      expect(screen.getByRole("button", { name: `Heal ${expected} HP` })).toBeEnabled()
    }
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it("resets a cleared number field to one without confirming", () => {
    const { onConfirm } = renderPicker()
    const input = screen.getByRole("spinbutton")
    fireEvent.change(input, { target: { value: "5" } })
    fireEvent.change(input, { target: { value: "" } })

    expect(input).toHaveValue(1)
    expect(screen.getByRole("slider")).toHaveValue("1")
    expect(screen.getByRole("button", { name: "Heal 1 HP" })).toBeEnabled()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it("confirms a clamped amount with Enter, but not other keys, before blur", () => {
    const { onConfirm } = renderPicker()
    const input = screen.getByRole("spinbutton")
    fireEvent.change(input, { target: { value: "99" } })
    fireEvent.keyDown(input, { key: "ArrowRight" })
    expect(onConfirm).not.toHaveBeenCalled()
    fireEvent.keyDown(input, { key: "Enter" })

    expect(onConfirm).toHaveBeenCalledExactlyOnceWith(8)
  })

  it.each(["Cancel", "Lay on Hands"])("cancels via the %s button without spending points", (name) => {
    const { onCancel, onConfirm } = renderPicker()
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "4" } })
    fireEvent.click(screen.getByRole("button", { name }))

    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it("disables the action anchor while keeping cancellation available", () => {
    const { onCancel, onConfirm } = renderPicker({ disabled: true })
    const anchor = screen.getByRole("button", { name: "Lay on Hands" })
    expect(anchor).toBeDisabled()
    fireEvent.click(anchor)
    expect(onCancel).not.toHaveBeenCalled()

    const cancel = screen.getByRole("button", { name: "Cancel" })
    expect(cancel).toBeEnabled()
    fireEvent.click(cancel)
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
