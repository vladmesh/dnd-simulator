import type { JsonSchema } from "@/types/api"

// ---------------------------------------------------------------------------
// JSON-schema resolution helpers (shared by SchemaForm and its subfields)
// ---------------------------------------------------------------------------

/** Resolve a $ref like "#/$defs/Foo" against the root schema's $defs. */
export function resolveRef(ref: string, rootDefs: Record<string, JsonSchema>): JsonSchema {
  const name = ref.replace("#/$defs/", "")
  const resolved = rootDefs[name]
  if (!resolved) throw new Error(`Unresolved $ref: ${ref}`)
  return resolved
}

/** Resolve a property schema: follow $ref, unwrap anyOf-with-null. */
export function resolveProperty(
  prop: JsonSchema,
  rootDefs: Record<string, JsonSchema>,
): JsonSchema {
  // Follow $ref
  if (prop.$ref) {
    const resolved = resolveRef(prop.$ref, rootDefs)
    // Merge title/default from the referencing property
    return { ...resolved, title: prop.title || resolved.title, default: prop.default ?? resolved.default }
  }
  // Unwrap anyOf [{type: X}, {type: null}] → {type: X}
  if (prop.anyOf) {
    const nonNull = prop.anyOf.filter((s) => s.type !== "null")
    if (nonNull.length === 1) {
      const unwrapped = nonNull[0]
      // If the non-null branch is a $ref, resolve it
      if (unwrapped.$ref) {
        const resolved = resolveRef(unwrapped.$ref, rootDefs)
        return { ...resolved, title: prop.title || resolved.title, default: prop.default ?? resolved.default }
      }
      // Check if it's an array with $ref items
      if (unwrapped.type === "array" && unwrapped.items?.$ref) {
        const resolvedItems = resolveRef(unwrapped.items.$ref, rootDefs)
        return {
          ...unwrapped,
          items: resolvedItems,
          title: prop.title || unwrapped.title,
          default: prop.default ?? unwrapped.default,
        }
      }
      return { ...unwrapped, title: prop.title || unwrapped.title, default: prop.default ?? unwrapped.default }
    }
  }
  return prop
}

/** Check if a schema represents a localized text field (object with additionalProperties: {type: string}). */
export function isLocalizedText(schema: JsonSchema): boolean {
  if (schema["x-localized"]) return true
  if (schema.type !== "object") return false
  if (schema.properties && Object.keys(schema.properties).length > 0) return false
  const ap = schema.additionalProperties
  return typeof ap === "object" && ap.type === "string"
}

/** Build default values from a JSON schema's properties. */
export function buildDefaults(
  schema: JsonSchema,
  rootDefs: Record<string, JsonSchema>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  const props = schema.properties ?? {}
  for (const [key, rawProp] of Object.entries(props)) {
    const prop = resolveProperty(rawProp, rootDefs)
    if (prop.default !== undefined) {
      result[key] = prop.default
    } else if (prop.type === "boolean") {
      result[key] = false
    } else if (prop.type === "array") {
      result[key] = []
    }
  }
  return result
}
