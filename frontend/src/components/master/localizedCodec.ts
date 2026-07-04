// ---------------------------------------------------------------------------
// Localized-text codec: {lang: value} on the wire ↔ flat string in the form.
// ---------------------------------------------------------------------------

/** Unwrap a stored localized value `{lang: text}` into the flat string the form edits. */
export function decodeLocalized(value: unknown, lang: string): string {
  if (typeof value === "object" && value !== null) {
    return (value as Record<string, string>)[lang] ?? ""
  }
  return typeof value === "string" ? value : ""
}

/** Wrap a flat form string back into the stored `{lang: text}` shape. */
export function encodeLocalized(value: string, lang: string): Record<string, string> {
  return { [lang]: value }
}
