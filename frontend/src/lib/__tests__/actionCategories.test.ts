import { describe, it, expect } from "vitest"
import { categorizeActions } from "../actionCategories"
import type { ActionInfo } from "@/types/game"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeAction(name: string, costType = "action", params: { name: string; type: string; required: boolean }[] = []): ActionInfo {
  return { name, description: `${name} action`, params, cost_type: costType }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("categorizeActions", () => {
  it("categorizes combat actions into correct groups", () => {
    const actions: ActionInfo[] = [
      makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
      makeAction("dodge", "action"),
      makeAction("dash", "action"),
      makeAction("disengage", "action"),
      makeAction("move", "movement"),
      makeAction("end_turn", "free"),
      makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }]),
      makeAction("equip", "free", [{ name: "weapon_id", type: "string", required: true }]),
      makeAction("second_wind", "bonus_action"),
      makeAction("say", "free"),
    ]

    const groups = categorizeActions(actions)
    const coreNames = groups.core.map((a) => a.name)
    expect(coreNames).toContain("attack")
    expect(coreNames).toContain("dodge")
    expect(coreNames).toContain("dash")
    expect(coreNames).toContain("disengage")
    // flee not in input — correctly absent from core
    expect(coreNames).not.toContain("flee")

    expect(groups.consumables.map((a) => a.name)).toContain("use_item")
    expect(groups.classFeatures.map((a) => a.name)).toContain("second_wind")
    expect(groups.inventory.map((a) => a.name)).toContain("equip")
    expect(groups.other.map((a) => a.name)).toContain("say")
    expect(groups.endTurn?.name).toBe("end_turn")
  })

  it("categorizes peaceful actions into correct groups", () => {
    const actions: ActionInfo[] = [
      makeAction("say", "free"),
      makeAction("wait", "free"),
      makeAction("idle", "free"),
      makeAction("use_item", "action", [{ name: "item_id", type: "string", required: true }]),
      makeAction("equip", "free", [{ name: "weapon_id", type: "string", required: true }]),
    ]

    const groups = categorizeActions(actions)
    expect(groups.core).toHaveLength(0)
    expect(groups.other.map((a) => a.name)).toContain("say")
    expect(groups.other.map((a) => a.name)).toContain("wait")
    expect(groups.other.map((a) => a.name)).toContain("idle")
    expect(groups.consumables.map((a) => a.name)).toContain("use_item")
    expect(groups.inventory.map((a) => a.name)).toContain("equip")
  })

  it("returns all groups empty when given empty actions", () => {
    const groups = categorizeActions([])
    expect(groups.core).toHaveLength(0)
    expect(groups.consumables).toHaveLength(0)
    expect(groups.classFeatures).toHaveLength(0)
    expect(groups.inventory).toHaveLength(0)
    expect(groups.other).toHaveLength(0)
    expect(groups.endTurn).toBeUndefined()
  })

  it("puts unknown actions into other (forward-compatible)", () => {
    const actions: ActionInfo[] = [
      makeAction("some_future_action", "action"),
      makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
    ]

    const groups = categorizeActions(actions)
    expect(groups.other.map((a) => a.name)).toContain("some_future_action")
    expect(groups.core.map((a) => a.name)).toContain("attack")
  })

  it("categorizes lay_on_hands as class feature", () => {
    const actions: ActionInfo[] = [
      makeAction("lay_on_hands", "action", [{ name: "target_id", type: "string", required: true }]),
      makeAction("second_wind", "bonus_action"),
      makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
    ]

    const groups = categorizeActions(actions)
    expect(groups.classFeatures.map((a) => a.name)).toContain("lay_on_hands")
    expect(groups.classFeatures.map((a) => a.name)).toContain("second_wind")
    expect(groups.other.map((a) => a.name)).not.toContain("lay_on_hands")
  })

  it("includes flee in core actions", () => {
    const actions: ActionInfo[] = [
      makeAction("flee", "action"),
      makeAction("attack", "action", [{ name: "target_id", type: "string", required: true }]),
    ]
    const groups = categorizeActions(actions)
    expect(groups.core.map((a) => a.name)).toContain("flee")
    expect(groups.core.map((a) => a.name)).toContain("attack")
  })
})
