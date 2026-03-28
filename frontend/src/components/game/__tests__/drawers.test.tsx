import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"
import "@/i18n"
import { ConsumableDrawer } from "../action-bar/ConsumableDrawer"
import { ClassFeatureDrawer } from "../action-bar/ClassFeatureDrawer"
import { InventoryDrawer } from "../action-bar/InventoryDrawer"
import type { ActionInfo, ItemInfo } from "@/types/game"

function makeAction(
  name: string,
  costType = "action",
  params: { name: string; type: string; required: boolean }[] = [],
): ActionInfo {
  return { name, description: `${name} desc`, params, cost_type: costType }
}

const potions: ItemInfo[] = [
  { id: "pot_1", name: "Healing Potion", item_type: "potion", description: "Heals 2d4+2 HP" },
  { id: "pot_2", name: "Greater Healing", item_type: "potion", description: "Heals 4d4+4 HP" },
]

// ---------------------------------------------------------------------------
// ConsumableDrawer
// ---------------------------------------------------------------------------

describe("ConsumableDrawer", () => {
  it("renders item count badge", () => {
    const { container } = render(
      <ConsumableDrawer
        items={potions}
        isOpen={false}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={vi.fn()}
      />,
    )
    const btn = container.querySelector("[data-drawer='consumables']")
    expect(btn).toBeTruthy()
    expect(btn!.textContent).toContain("2")
  })

  it("clicking potion sends use_item with correct item_id", () => {
    const sendAction = vi.fn()
    render(
      <ConsumableDrawer
        items={potions}
        isOpen={true}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={sendAction}
      />,
    )
    fireEvent.click(screen.getByText("Healing Potion"))
    expect(sendAction).toHaveBeenCalledWith("use_item", { item_id: "pot_1" })
  })

  it("shows potion descriptions in open popup", () => {
    render(
      <ConsumableDrawer
        items={potions}
        isOpen={true}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={vi.fn()}
      />,
    )
    expect(screen.getByText("Heals 2d4+2 HP")).toBeTruthy()
    expect(screen.getByText("Heals 4d4+4 HP")).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// ClassFeatureDrawer
// ---------------------------------------------------------------------------

describe("ClassFeatureDrawer", () => {
  const features = [makeAction("second_wind", "bonus_action")]

  it("renders feature count", () => {
    const { container } = render(
      <ClassFeatureDrawer
        actions={features}
        isOpen={false}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={vi.fn()}
      />,
    )
    const btn = container.querySelector("[data-drawer='class-features']")
    expect(btn).toBeTruthy()
    expect(btn!.textContent).toContain("1")
  })

  it("clicking feature sends action", () => {
    const sendAction = vi.fn()
    const { container } = render(
      <ClassFeatureDrawer
        actions={features}
        isOpen={true}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={sendAction}
      />,
    )
    const popup = container.querySelector("[data-drawer-popup='class-features']")
    const btn = popup!.querySelector("button")
    fireEvent.click(btn!)
    expect(sendAction).toHaveBeenCalledWith("second_wind")
  })

  it("shows cost badge for bonus_action features", () => {
    const { container } = render(
      <ClassFeatureDrawer
        actions={features}
        isOpen={true}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={vi.fn()}
      />,
    )
    const popup = container.querySelector("[data-drawer-popup='class-features']")
    expect(popup!.textContent).toContain("bonus_action")
  })
})

// ---------------------------------------------------------------------------
// InventoryDrawer
// ---------------------------------------------------------------------------

describe("InventoryDrawer", () => {
  const weapons: ItemInfo[] = [
    { id: "w1", name: "Sword", item_type: "weapon", description: "A sharp sword" },
  ]
  const equipAction = makeAction("equip", "free", [{ name: "weapon_id", type: "string", required: true }])

  it("renders equip actions count", () => {
    const { container } = render(
      <InventoryDrawer
        actions={[equipAction]}
        items={weapons}
        isOpen={false}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={vi.fn()}
      />,
    )
    const btn = container.querySelector("[data-drawer='inventory']")
    expect(btn).toBeTruthy()
  })

  it("clicking weapon sends equip with weapon_id", () => {
    const sendAction = vi.fn()
    render(
      <InventoryDrawer
        actions={[equipAction]}
        items={weapons}
        isOpen={true}
        onToggle={vi.fn()}
        disabled={false}
        sendAction={sendAction}
      />,
    )
    // Find button with weapon name in it
    const popup = screen.getByText(/Sword/)
    fireEvent.click(popup.closest("button")!)
    expect(sendAction).toHaveBeenCalledWith("equip", { weapon_id: "w1" })
  })
})
