import { describe, it, expect } from "vitest"
import { resolveProperty, isLocalizedText, buildDefaults } from "../schemaResolve"
import type { JsonSchema } from "@/types/api"

describe("resolveProperty", () => {
  it("unwraps anyOf [{type}, {type:null}] to the non-null branch", () => {
    const prop: JsonSchema = { anyOf: [{ type: "string" }, { type: "null" }], title: "Name" }
    expect(resolveProperty(prop, {})).toMatchObject({ type: "string", title: "Name" })
  })

  it("resolves a $ref and merges the referencing title/default", () => {
    const defs = { Foo: { type: "object", title: "Foo" } as JsonSchema }
    const prop: JsonSchema = { $ref: "#/$defs/Foo", title: "Bar" }
    expect(resolveProperty(prop, defs)).toMatchObject({ type: "object", title: "Bar" })
  })

  it("returns the prop unchanged when no $ref/anyOf", () => {
    const prop: JsonSchema = { type: "integer" }
    expect(resolveProperty(prop, {})).toBe(prop)
  })
})

describe("isLocalizedText", () => {
  it("is true for x-localized", () => {
    expect(isLocalizedText({ "x-localized": true })).toBe(true)
  })
  it("is true for object with additionalProperties string", () => {
    expect(isLocalizedText({ type: "object", additionalProperties: { type: "string" } })).toBe(true)
  })
  it("is false for a plain string field", () => {
    expect(isLocalizedText({ type: "string" })).toBe(false)
  })
})

describe("buildDefaults", () => {
  it("uses declared defaults, false for booleans, [] for arrays", () => {
    const schema: JsonSchema = {
      type: "object",
      properties: {
        a: { type: "string", default: "x" },
        b: { type: "boolean" },
        c: { type: "array", items: { type: "string" } },
        d: { type: "integer" },
      },
    }
    expect(buildDefaults(schema, {})).toEqual({ a: "x", b: false, c: [] })
  })
})
