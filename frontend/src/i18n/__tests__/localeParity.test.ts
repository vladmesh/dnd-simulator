import ts from "typescript"
import { describe, expect, it } from "vitest"
import { defaultNS, resources } from "@/i18n"

type Strings = Map<string, string>
type SourceGap = { location: string; key: string }

// BUG: These source keys currently rely on English defaultValue/fallback text
// instead of entries in the English resources. Do not allow any additional gaps.
const KNOWN_GAPS = {
  sourceKeys: [
    "game:disengaging_tooltip",
    "game:reaction_prompt_title",
    "game:reaction_skip",
    "master:no_llm_key",
  ],
}

function strings(value: unknown, path = "", out: Strings = new Map()): Strings {
  if (typeof value === "string") out.set(path, value)
  else if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      strings(child, path ? `${path}.${key}` : key, out)
    }
  }
  return out
}

function baseKey(key: string): string {
  return key.replace(/_(one|few|many|other|zero|two)$/, "")
}

function groups(entries: Strings): Map<string, string[]> {
  const out = new Map<string, string[]>()
  for (const [key, value] of entries) {
    const base = baseKey(key)
    out.set(base, [...(out.get(base) ?? []), value])
  }
  return out
}

function placeholders(values: string[]): string[] {
  return [...new Set(values.flatMap((value) =>
    [...value.matchAll(/\{\{\s*([^{}]+?)\s*\}\}/g)].map((match) =>
      // i18next also supports unescaped variables and formatters.
      match[1].replace(/^-\s*/, "").split(",")[0].trim(),
    ),
  ))].sort()
}

const tables = Object.fromEntries(
  Object.entries(resources).map(([locale, namespaces]) => [
    locale,
    new Map(Object.entries(namespaces).map(([ns, table]) => [ns, strings(table)])),
  ]),
)
const en = tables.en
const ru = tables.ru
const namespaces = [...new Set([...en.keys(), ...ru.keys()])].sort()

const sources = import.meta.glob<string>("/src/**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
})

function literal(node: ts.Node | undefined): string | undefined {
  return node && ts.isStringLiteralLike(node) ? node.text : undefined
}

function isCall(node: ts.Node, name: string): node is ts.CallExpression {
  return ts.isCallExpression(node) && ts.isIdentifier(node.expression) &&
    node.expression.text === name
}

function sourceKeyGaps(): SourceGap[] {
  const offending: SourceGap[] = []
  for (const [file, source] of Object.entries(sources).sort()) {
    if (/(^|\/)(__tests__|tests?|__mocks__)(\/|$)|\.(test|spec)\.[cm]?[jt]sx?$/.test(file)) continue
    // Parse rather than regex-match calls, so comments and dynamic expressions
    // cannot masquerade as literal t(...) usages.
    const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true)
    const defaults = new Set<string | undefined>()
    function findDefaults(node: ts.Node): void {
      if (isCall(node, "useTranslation")) {
        const arg = node.arguments[0]
        defaults.add(arg === undefined ? defaultNS : literal(
          ts.isArrayLiteralExpression(arg) ? arg.elements[0] : arg,
        ))
      }
      ts.forEachChild(node, findDefaults)
    }
    findDefaults(ast)
    // A file-wide default is safe only when every hook agrees. In files with
    // ambiguous/dynamic defaults (e.g. EventLog), check namespaced literals only.
    // This deliberately avoids guessing across component scopes or dynamic keys.
    const fileDefault = defaults.size === 1 ? [...defaults][0] : undefined

    function visit(node: ts.Node): void {
      if (isCall(node, "t")) {
        const key = literal(node.arguments[0])
        if (key !== undefined) {
          // Options may follow either the key or a literal fallback string.
          const options = node.arguments.length > 1 ? node.arguments.at(-1) : undefined
          const nsOption = options && ts.isObjectLiteralExpression(options)
            ? options.properties.find((property) =>
              ts.isPropertyAssignment(property) &&
              (ts.isIdentifier(property.name) ? property.name.text : literal(property.name)) === "ns",
            )
            : undefined
          const optionDefault = nsOption && ts.isPropertyAssignment(nsOption)
            ? literal(nsOption.initializer)
            : undefined
          const colon = key.indexOf(":")
          const ns = colon >= 0 ? key.slice(0, colon) : nsOption ? optionDefault : fileDefault
          const path = colon >= 0 ? key.slice(colon + 1) : key
          if (ns !== undefined) {
            const entries = en.get(ns)
            // A plural base is callable with { count } even without a raw base
            // entry. Explicit suffixed keys must themselves exist, however.
            const exists = entries?.has(path) || (baseKey(path) === path &&
              [...(entries?.keys() ?? [])].some((entry) => baseKey(entry) === path))
            if (!exists) {
              const { line } = ast.getLineAndCharacterOfPosition(node.getStart(ast))
              offending.push({ location: `${file}:${line + 1}`, key: `${ns}:${path}` })
            }
          }
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(ast)
  }
  return offending
}

const missingSourceKeys = sourceKeyGaps()

describe("English/Russian locale parity", () => {
  it("has the same namespaces in both directions", () => {
    const offending = namespaces.flatMap((ns) => [
      ...(!en.has(ns) ? [`en: missing namespace ${ns}`] : []),
      ...(!ru.has(ns) ? [`ru: missing namespace ${ns}`] : []),
    ])
    expect(offending).toEqual([])
  })

  it("has identical nested keys, comparing plural forms by base key", () => {
    const offending: string[] = []
    for (const ns of namespaces) {
      const enKeys = groups(en.get(ns) ?? new Map())
      const ruKeys = groups(ru.get(ns) ?? new Map())
      for (const key of [...new Set([...enKeys.keys(), ...ruKeys.keys()])].sort()) {
        if (!enKeys.has(key)) offending.push(`en: missing ${ns}:${key}`)
        if (!ruKeys.has(key)) offending.push(`ru: missing ${ns}:${key}`)
      }
    }
    expect(offending).toEqual([])
  })

  it("has no empty or whitespace-only translations in either locale", () => {
    const offending: string[] = []
    for (const [locale, namespaces] of Object.entries(tables)) {
      for (const [ns, entries] of namespaces) {
        for (const [key, value] of entries) {
          if (!value.trim()) offending.push(`${locale}:${ns}:${key}`)
        }
      }
    }
    expect(offending).toEqual([])
  })

  it("has matching interpolation placeholder sets (unioned across plural forms)", () => {
    const offending: Array<{ key: string; en: string[]; ru: string[] }> = []
    for (const ns of namespaces) {
      const enGroups = groups(en.get(ns) ?? new Map())
      const ruGroups = groups(ru.get(ns) ?? new Map())
      for (const [key, values] of enGroups) {
        const translated = ruGroups.get(key)
        // Missing keys are reported by the key-parity test instead.
        if (translated === undefined) continue
        const enPlaceholders = placeholders(values)
        const ruPlaceholders = placeholders(translated)
        if (JSON.stringify(enPlaceholders) !== JSON.stringify(ruPlaceholders)) {
          offending.push({ key: `${ns}:${key}`, en: enPlaceholders, ru: ruPlaceholders })
        }
      }
    }
    expect(offending).toEqual([])
  })

  it("defines static source translation keys in English except documented gaps", () => {
    const offending = missingSourceKeys.filter((gap) => !KNOWN_GAPS.sourceKeys.includes(gap.key))
    expect(offending).toEqual([])
  })

  it("keeps the known-gap list limited to currently missing source keys", () => {
    const offending = KNOWN_GAPS.sourceKeys.filter((key) =>
      !missingSourceKeys.some((gap) => gap.key === key),
    )
    expect(offending).toEqual([])
  })

  it.fails("documents the existing missing English source translations", () => {
    // BUG: game:disengaging_tooltip (BudgetDisplay), game:reaction_prompt_title
    // and game:reaction_skip (ReactionPrompt), master:no_llm_key (CreatureList)
    // have fallback text but no English resource entries (nor Russian entries).
    const offending = missingSourceKeys.filter((gap) => KNOWN_GAPS.sourceKeys.includes(gap.key))
    expect(offending).toEqual([])
  })
})
