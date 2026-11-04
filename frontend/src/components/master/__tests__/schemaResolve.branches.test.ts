import { describe, it, expect } from "vitest"
import { resolveRef, resolveProperty, isLocalizedText, buildDefaults } from "../schemaResolve"
import type { JsonSchema } from "@/types/api"

describe("schema resolution edge cases", () => {
  it("reports unresolved references, including nullable branches and array items", () => {
    const ref = "#/$defs/Missing"
    const props: JsonSchema[] = [
      { $ref: ref },
      { anyOf: [{ $ref: ref }, { type: "null" }] },
      { anyOf: [{ type: "array", items: { $ref: ref } }, { type: "null" }] },
    ]

    expect(() => resolveRef(ref, {})).toThrow(`Unresolved $ref: ${ref}`)
    for (const prop of props) {
      expect(() => resolveProperty(prop, {})).toThrow(`Unresolved $ref: ${ref}`)
    }
  })

  it("inherits reference metadata for empty titles and nullish defaults but preserves falsy defaults", () => {
    const definition: JsonSchema = { type: "string", title: "Inherited", default: "fallback" }
    const defs = { Value: definition }

    for (const defaultValue of [undefined, null]) {
      expect(resolveProperty({ $ref: "#/$defs/Value", title: "", default: defaultValue }, defs))
        .toEqual(definition)
    }
    for (const defaultValue of [false, 0, ""]) {
      expect(resolveProperty({ $ref: "#/$defs/Value", title: "Override", default: defaultValue }, defs))
        .toEqual({ ...definition, title: "Override", default: defaultValue })
    }
  })

  it("resolves nullable references with inherited or overridden metadata", () => {
    const definition: JsonSchema = { type: "boolean", title: "Enabled", default: true }
    const defs = { Flag: definition }
    const prop: JsonSchema = { anyOf: [{ $ref: "#/$defs/Flag" }, { type: "null" }] }

    expect(resolveProperty(prop, defs)).toEqual(definition)
    expect(resolveProperty({ ...prop, title: "", default: null }, defs)).toEqual(definition)
    expect(resolveProperty({ ...prop, title: "Active", default: false }, defs))
      .toEqual({ ...definition, title: "Active", default: false })
  })

  it("resolves nullable array item references and merges array metadata", () => {
    const item: JsonSchema = { type: "object", properties: { name: { type: "string" } } }
    const array: JsonSchema = {
      type: "array",
      items: { $ref: "#/$defs/Item" },
      title: "Items",
      default: [{ name: "Potion" }],
    }
    const prop: JsonSchema = { anyOf: [array, { type: "null" }] }
    const defs = { Item: item }
    const expected = { ...array, items: item }

    expect(resolveProperty(prop, defs)).toEqual(expected)
    expect(resolveProperty({ ...prop, title: "", default: null }, defs)).toEqual(expected)
    expect(resolveProperty({ ...prop, title: "Inventory", default: [] }, defs))
      .toEqual({ ...expected, title: "Inventory", default: [] })
  })

  it("unwraps nullable arrays without item references without changing their item schema", () => {
    const arrays: JsonSchema[] = [
      { type: "array" },
      { type: "array", items: { type: "string" } },
    ]

    for (const array of arrays) {
      expect(resolveProperty({ anyOf: [{ type: "null" }, array] }, {}))
        .toEqual({ ...array, title: undefined, default: undefined })
    }
  })

  it("inherits nullable inline metadata and keeps an explicit zero default", () => {
    const branch: JsonSchema = { type: "integer", title: "Count", default: 3 }
    const prop: JsonSchema = { anyOf: [{ type: "null" }, branch] }

    expect(resolveProperty(prop, {})).toEqual(branch)
    expect(resolveProperty({ ...prop, title: "", default: null }, {})).toEqual(branch)
    expect(resolveProperty({ ...prop, default: 0 }, {})).toEqual({ ...branch, default: 0 })
  })

  it("leaves empty, null-only, and ambiguous unions unchanged", () => {
    const unions: JsonSchema[][] = [
      [],
      [{ type: "null" }],
      [{ type: "string" }, { type: "integer" }, { type: "null" }],
    ]

    for (const anyOf of unions) {
      const prop: JsonSchema = { anyOf, title: "Union", default: null }
      expect(resolveProperty(prop, {})).toBe(prop)
    }
  })
})

describe("localized text edge cases", () => {
  it("rejects structured objects unless localization is explicitly enabled", () => {
    const schema: JsonSchema = {
      type: "object",
      properties: { name: { type: "string" } },
      additionalProperties: { type: "string" },
    }

    expect(isLocalizedText(schema)).toBe(false)
    expect(isLocalizedText({ ...schema, "x-localized": false })).toBe(false)
    expect(isLocalizedText({ ...schema, "x-localized": true })).toBe(true)
  })

  it("accepts empty property maps only with string-valued additional properties", () => {
    expect(isLocalizedText({
      type: "object",
      properties: {},
      additionalProperties: { type: "string" },
    })).toBe(true)

    const additionalProperties: JsonSchema["additionalProperties"][] = [
      undefined, false, true, {}, { type: "number" },
    ]
    for (const value of additionalProperties) {
      expect(isLocalizedText({ type: "object", properties: {}, additionalProperties: value }))
        .toBe(false)
    }
  })
})

describe("default construction edge cases", () => {
  it("returns no defaults when properties are absent", () => {
    expect(buildDefaults({ type: "object" }, {})).toEqual({})
  })

  it("builds defaults from references and nullable schemas without losing falsy values", () => {
    const defs: Record<string, JsonSchema> = {
      Count: { type: "integer", default: 3 },
      Optional: { type: "string", default: null },
      Item: { type: "object" },
    }
    const schema: JsonSchema = {
      properties: {
        count: { $ref: "#/$defs/Count", default: 0 },
        optional: { $ref: "#/$defs/Optional" },
        enabled: { anyOf: [{ type: "boolean" }, { type: "null" }] },
        items: { anyOf: [{ type: "array", items: { $ref: "#/$defs/Item" } }, { type: "null" }] },
        label: { anyOf: [{ type: "string" }, { type: "null" }], default: "" },
        unset: { anyOf: [{ type: "integer" }, { type: "null" }] },
      },
    }

    expect(buildDefaults(schema, defs)).toEqual({
      count: 0,
      optional: null,
      enabled: false,
      items: [],
      label: "",
    })
  })
})
