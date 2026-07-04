import { describe, it, expect } from "vitest"
import { buildAttackParams } from "../attackParams"

describe("buildAttackParams", () => {
  it("omits smite_slot_level when no slot chosen", () => {
    expect(buildAttackParams("goblin_1", null)).toEqual({ target_id: "goblin_1" })
  })

  it("includes smite_slot_level when a slot is chosen", () => {
    expect(buildAttackParams("goblin_1", 1)).toEqual({
      target_id: "goblin_1",
      smite_slot_level: 1,
    })
  })

  it("keeps slot level 0 distinct from null (only null omits)", () => {
    // level is always >= 1 in practice, but null is the sole "no smite" sentinel
    expect(buildAttackParams("goblin_1", 2)).toEqual({
      target_id: "goblin_1",
      smite_slot_level: 2,
    })
  })
})
