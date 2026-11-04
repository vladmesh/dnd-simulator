import { render, screen } from "@testing-library/react"
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest"
import i18n from "@/i18n"
import type { WeaponProps } from "@/types/game"
import { ItemDetails } from "../ItemDetails"

// This card is presentation-only; no transport should be needed to render it.
vi.mock("@/transport/apiClient", () => ({ api: {} }))

const originalLanguage = i18n.language
const basicWeapon: WeaponProps = {
  kind: "weapon",
  damage: [{ dice: "1d4", type: "piercing" }],
  reach: 5,
  category: "simple",
}

describe("ItemDetails — additional display branches", () => {
  beforeAll(async () => {
    await i18n.changeLanguage("en")
  })

  afterAll(async () => {
    await i18n.changeLanguage(originalLanguage)
  })

  // Details intentionally stay in the DOM before hover; no loading or actions exist here.
  it("renders the child immediately without inventing details for an empty item", () => {
    render(<ItemDetails item={{}}>Unidentified relic</ItemDetails>)

    expect(screen.getByText("Unidentified relic")).toBeInTheDocument()
    expect(document.body).toHaveTextContent(/^Unidentified relic$/)
  })

  it("shows a zero price and hint without props, and omits null price and empty hint", () => {
    const { rerender } = render(
      <ItemDetails item={{ props: null, description: "", price: 0 }} align="right" hint="Not for sale">
        Gift
      </ItemDetails>,
    )

    expect(screen.getByText("Price: 0g")).toBeInTheDocument()
    expect(screen.getByText("Not for sale")).toBeInTheDocument()

    rerender(
      <ItemDetails item={{ props: null, price: null }} hint="">
        Gift
      </ItemDetails>,
    )

    expect(screen.queryByText(/^Price:/)).not.toBeInTheDocument()
    expect(screen.queryByText("Not for sale")).not.toBeInTheDocument()
    expect(document.body).toHaveTextContent(/^Gift$/)
  })

  it("renders a shield's AC bonus instead of its unstructured description", () => {
    render(
      <ItemDetails item={{ props: { kind: "shield", ac_bonus: 2 }, description: "Old shield text" }}>
        Shield
      </ItemDetails>,
    )

    expect(screen.getByText("+2 AC")).toBeInTheDocument()
    expect(screen.queryByText("Old shield text")).not.toBeInTheDocument()
  })

  it("lists finesse and light properties and falls back to raw condition names", () => {
    render(
      <ItemDetails
        item={{
          props: {
            ...basicWeapon,
            is_finesse: true,
            is_light: true,
            conditions: ["poisoned", "silvered"],
          },
        }}
      >
        Dagger
      </ItemDetails>,
    )

    expect(screen.getByText("Finesse, Light")).toBeInTheDocument()
    expect(screen.getByText("poisoned")).toBeInTheDocument()
    expect(screen.getByText("silvered")).toBeInTheDocument()
  })

  it("lists two-handed and heavy properties and preserves unknown weapon labels", () => {
    render(
      <ItemDetails
        item={{
          props: {
            ...basicWeapon,
            damage: [{ dice: "2d6", type: "starlight" }],
            category: "exotic",
            ability: "luck",
            is_two_handed: true,
            is_heavy: true,
          },
        }}
      >
        Star hammer
      </ItemDetails>,
    )

    expect(screen.getByText("Two-handed, Heavy")).toBeInTheDocument()
    expect(screen.getByText("Damage: 2d6 starlight")).toBeInTheDocument()
    expect(screen.getByText("exotic")).toBeInTheDocument()
    expect(screen.getByText("Ability: LUCK")).toBeInTheDocument()
  })

  it("omits zero weapon modifiers, absent abilities and unset properties", () => {
    render(
      <ItemDetails item={{ props: { ...basicWeapon, modifier: 0, ability: null } }}>
        Plain dart
      </ItemDetails>,
    )

    expect(screen.getByText("Damage: 1d4 piercing")).toBeInTheDocument()
    expect(screen.queryByText(/\+0/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Ability:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Finesse|Two-handed|Light|Heavy|Magic/)).not.toBeInTheDocument()
  })

  it("omits both missing and null armor dex caps and preserves an unknown category", () => {
    const armor = { kind: "armor", base_ac: 13, category: "crystalline" } as const
    const { rerender } = render(
      <ItemDetails item={{ props: armor }}>Crystal armor</ItemDetails>,
    )

    expect(screen.getByText("crystalline")).toBeInTheDocument()
    expect(screen.queryByText(/^Max DEX bonus:/)).not.toBeInTheDocument()

    rerender(
      <ItemDetails item={{ props: { ...armor, max_dex_bonus: null } }}>
        Crystal armor
      </ItemDetails>,
    )

    expect(screen.getByText("crystalline")).toBeInTheDocument()
    expect(screen.queryByText(/^Max DEX bonus:/)).not.toBeInTheDocument()
  })

  it("formats negative and zero additive modifiers without a plus and preserves unknown stats", () => {
    render(
      <ItemDetails
        item={{
          props: {
            kind: "accessory",
            slot: "feet",
            modifiers: [
              { stat: "speed", op: "add", value: -5 },
              { stat: "initiative", op: "add", value: 0 },
              { stat: "luck", op: "add", value: 2 },
            ],
          },
        }}
      >
        Weighted boots
      </ItemDetails>,
    )

    expect(screen.getByText("-5 Speed")).toBeInTheDocument()
    expect(screen.getByText("0 Initiative")).toBeInTheDocument()
    expect(screen.getByText("+2 luck")).toBeInTheDocument()
  })

  it("formats an override modifier as a fixed stat value", () => {
    render(
      <ItemDetails
        item={{
          props: {
            kind: "accessory",
            slot: "head",
            modifiers: [{ stat: "ac", op: "override", value: 19 }],
          },
        }}
      >
        Protective circlet
      </ItemDetails>,
    )

    expect(screen.getByText("AC = 19")).toBeInTheDocument()
  })

  it("translates non-numeric modifier operations and falls back for unknown ones", () => {
    render(
      <ItemDetails
        item={{
          props: {
            kind: "accessory",
            slot: "ring",
            modifiers: [
              { stat: "attack_roll", op: "advantage", value: 0 },
              { stat: "luck", op: "shimmer", value: 0 },
            ],
          },
        }}
      >
        Shimmering ring
      </ItemDetails>,
    )

    expect(screen.getByText("Attack roll: Advantage")).toBeInTheDocument()
    expect(screen.getByText("luck: shimmer")).toBeInTheDocument()
  })

  it("renders an unknown accessory slot with no modifiers or description fallback", () => {
    render(
      <ItemDetails
        item={{
          props: { kind: "accessory", slot: "cloak", modifiers: [] },
          description: "Old cloak text",
        }}
      >
        Traveler's cloak
      </ItemDetails>,
    )

    expect(screen.getByText("cloak")).toBeInTheDocument()
    expect(screen.queryByText("Old cloak text")).not.toBeInTheDocument()
  })
})
