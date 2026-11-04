import { describe, it, expect } from "vitest"
import type { AttackRollData, DamageComponentData } from "@/types/game"
import { extractAttackCardData } from "../attackCard"

// This module only extracts event data; it has no UI or API dependencies to mock.
function makeRoll(): AttackRollData {
  return {
    natural: 14,
    d20: { sides: 20, result: 14 },
    components: [{ source: "str", value: 3, dice: "" }],
    total: 17,
    advantage: false,
    disadvantage: false,
  }
}

describe("extractAttackCardData", () => {
  it("returns null when an event has no usable attack breakdown", () => {
    for (const attackRoll of [
      undefined,
      null,
      "14",
      {},
      { natural: "14", total: 17, d20: { sides: 20, result: 14 } },
      { natural: 14, total: "17", d20: { sides: 20, result: 14 } },
      { natural: 14, total: 17, d20: null },
    ]) {
      expect(extractAttackCardData({ attack_roll: attackRoll })).toBeNull()
    }
  })

  it("supplies defaults for missing or null optional event fields", () => {
    const attackRoll = makeRoll()
    for (const empty of [undefined, null]) {
      expect(extractAttackCardData({
        attack_roll: attackRoll,
        attacker_name: empty,
        attacker_id: empty,
        target_name: empty,
        target_id: empty,
        weapon: empty,
      })).toEqual({
        attackerName: "?",
        targetName: "?",
        weapon: "Attack",
        hit: false,
        critical: false,
        ac: 0,
        attackRoll,
        totalDamage: undefined,
        rolledDamage: undefined,
        damageComponents: undefined,
      })
    }
  })

  it("falls back to actor IDs when names are missing or null", () => {
    for (const name of [undefined, null]) {
      expect(extractAttackCardData({
        attack_roll: makeRoll(),
        attacker_name: name,
        attacker_id: "fighter-1",
        target_name: name,
        target_id: "goblin-2",
      })).toMatchObject({ attackerName: "fighter-1", targetName: "goblin-2" })
    }
  })

  it("preserves empty names and weapon instead of replacing them with fallbacks", () => {
    expect(extractAttackCardData({
      attack_roll: makeRoll(),
      attacker_name: "",
      attacker_id: "fighter-1",
      target_name: "",
      target_id: "goblin-2",
      weapon: "",
    })).toMatchObject({ attackerName: "", targetName: "", weapon: "" })
  })

  it("maps named event data and keeps dealt damage separate from rolled damage", () => {
    const attackRoll = makeRoll()
    const damageComponents: DamageComponentData[] = [{
      source: "weapon",
      dice: "1d8",
      dice_detail: [{ sides: 8, result: 6 }],
      amount: 6,
      type: "slashing",
    }]

    expect(extractAttackCardData({
      attacker_name: "Fighter",
      attacker_id: "fighter-1",
      target_name: "Goblin",
      target_id: "goblin-2",
      weapon: "Longsword",
      hit: true,
      critical: true,
      ac: 15,
      attack_roll: attackRoll,
      damage: 3,
      total_damage: 6,
      damage_components: damageComponents,
    })).toEqual({
      attackerName: "Fighter",
      targetName: "Goblin",
      weapon: "Longsword",
      hit: true,
      critical: true,
      ac: 15,
      attackRoll,
      totalDamage: 3,
      rolledDamage: 6,
      damageComponents,
    })
  })

  it("requires literal true for hit and critical, independently", () => {
    for (const value of [false, undefined, null, "true", 1]) {
      expect(extractAttackCardData({
        attack_roll: makeRoll(), hit: true, critical: value,
      })).toMatchObject({ hit: true, critical: false })
      expect(extractAttackCardData({
        attack_roll: makeRoll(), hit: value, critical: true,
      })).toMatchObject({ hit: false, critical: true })
    }
  })

  it("does not coerce nonnumeric AC or damage totals", () => {
    for (const value of [undefined, null, "12", false, {}, []]) {
      expect(extractAttackCardData({
        attack_roll: makeRoll(),
        ac: value,
        damage: value,
        total_damage: value,
      })).toMatchObject({ ac: 0, totalDamage: undefined, rolledDamage: undefined })
    }
  })

  it("preserves zero totals and extracts each optional damage total independently", () => {
    const attack_roll = makeRoll()
    expect(extractAttackCardData({ attack_roll, ac: 0, damage: 0 })).toMatchObject({
      ac: 0, totalDamage: 0, rolledDamage: undefined,
    })
    expect(extractAttackCardData({ attack_roll, total_damage: 0 })).toMatchObject({
      totalDamage: undefined, rolledDamage: 0,
    })
  })

  it("omits damage components when the payload is not an array", () => {
    for (const value of [undefined, null, {}, "1d8", 0]) {
      expect(extractAttackCardData({
        attack_roll: makeRoll(), damage_components: value,
      })).toMatchObject({ damageComponents: undefined })
    }
  })

  it("retains an explicitly empty damage breakdown", () => {
    expect(extractAttackCardData({
      attack_roll: makeRoll(), damage_components: [],
    })).toMatchObject({ damageComponents: [] })
  })
})
