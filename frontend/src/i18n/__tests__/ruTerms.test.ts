import { describe, expect, it } from "vitest"
import { resources } from "@/i18n"

function strings(value: unknown, path: string, out: Array<[string, string]>): void {
  if (typeof value === "string") out.push([path, value])
  else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) strings(v, `${path}.${k}`, out)
  }
}

describe("Russian UI terminology", () => {
  const entries: Array<[string, string]> = []
  for (const [ns, table] of Object.entries(resources.ru)) strings(table, ns, entries)

  it("calls Armor Class «КД» everywhere: no raw «AC» and no «КЗ»", () => {
    const offending = entries.filter(([, s]) => /\bAC\b|КЗ/.test(s))
    expect(offending).toEqual([])
  })
})
