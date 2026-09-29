/**
 * Compile-time contract for the GM creature request wire types against
 * `SpawnCreatureRequest` / `PatchCreatureRequest` in adapters/api/schemas.py.
 *
 * The assertions are checked by `tsc -b` (this file is part of the app project):
 * a drift in a field's requiredness, nullability or enum makes an `Assert<...>`
 * fail to compile, and each `@ts-expect-error` fails the build once its line
 * stops being an error.
 */
import { describe, it, expect } from "vitest"
import type { BrainType, EntityKind, PatchCreatureRequest, SpawnCreatureRequest } from "@/types/api"

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2) ? true : false
type Assert<T extends true> = T
type RequiredKeys<T> = { [K in keyof T]-?: object extends Pick<T, K> ? never : K }[keyof T]

// Enums mirror core/models.py::EntityKind and core/brain.py::BrainType.
export type EntityKindMatches = Assert<Equal<EntityKind, "player" | "npc" | "creature" | "container" | "monster">>
export type BrainTypeMatches = Assert<Equal<BrainType, "rule_based" | "llm">>

// SpawnCreatureRequest: exact field set, requiredness and nullability.
export type SpawnKeys = Assert<Equal<
  keyof SpawnCreatureRequest,
  | "id" | "name" | "entity_type" | "start_location" | "hp" | "ac" | "speed"
  | "attacks" | "ability_scores" | "combat_position"
  | "role" | "personality" | "settlement_id" | "ai" | "xp_value"
>>
export type SpawnRequired = Assert<Equal<
  RequiredKeys<SpawnCreatureRequest>,
  "id" | "name" | "entity_type" | "start_location" | "hp" | "ac" | "speed"
>>
export type SpawnFields = Assert<Equal<SpawnCreatureRequest, {
  id: string
  name: string
  entity_type: EntityKind
  start_location: string
  hp: number
  ac: number
  speed: number
  attacks?: Array<Record<string, unknown>> | null
  ability_scores?: Record<string, number> | null
  combat_position?: number[] | null
  role?: string | null
  personality?: string | null
  settlement_id?: string | null
  ai?: BrainType
  xp_value?: number | null
}>>

// PatchCreatureRequest: every field optional and nullable.
export type PatchRequired = Assert<Equal<RequiredKeys<PatchCreatureRequest>, never>>
export type PatchFields = Assert<Equal<PatchCreatureRequest, {
  current_hp?: number | null
  max_hp?: number | null
  ac?: number | null
  location_id?: string | null
  conditions?: string[] | null
  gold?: number | null
  level?: number | null
  experience?: number | null
  xp_value?: number | null
  resource_pools?: Array<Record<string, unknown>> | null
  personality?: string | null
}>>

const minimalSpawn: SpawnCreatureRequest = {
  id: "wolf_1", name: "Wolf", entity_type: "monster", start_location: "forest", hp: 11, ac: 13, speed: 40,
}

// @ts-expect-error hp is required by the server
export const missingHp: SpawnCreatureRequest = { ...minimalSpawn, hp: undefined }
// @ts-expect-error start_location is required by the server
export const missingLocation: SpawnCreatureRequest = { ...minimalSpawn, start_location: undefined }
// @ts-expect-error region_id is not a server field
export const withRegion: SpawnCreatureRequest = { ...minimalSpawn, region_id: "north" }
// @ts-expect-error entity_type must be an EntityKind
export const badKind: SpawnCreatureRequest = { ...minimalSpawn, entity_type: "dragon" }
// @ts-expect-error ai must be a BrainType
export const badBrain: SpawnCreatureRequest = { ...minimalSpawn, ai: "player" }
// @ts-expect-error ai has a server default but is not nullable
export const nullBrain: SpawnCreatureRequest = { ...minimalSpawn, ai: null }
// @ts-expect-error experience is a patch field, not a spawn field
export const spawnExperience: SpawnCreatureRequest = { ...minimalSpawn, experience: 10 }
// @ts-expect-error speed is not a patch field
export const patchSpeed: PatchCreatureRequest = { speed: 30 }

describe("GM creature request wire types", () => {
  it("accepts the minimal spawn payload the server requires", () => {
    expect(Object.keys(minimalSpawn).sort()).toEqual(
      ["ac", "entity_type", "hp", "id", "name", "speed", "start_location"],
    )
  })
})
