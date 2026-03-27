import { useCallback, useEffect, useState } from "react"
import { api } from "@/transport/apiClient"
import type { CatalogEntry, JsonSchema } from "@/types/api"
import { Button } from "@/components/ui/button"
import { Loader2, Eye } from "lucide-react"
import { SchemaForm } from "./SchemaForm"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CatalogBrowserProps {
  catalogType: string
  /** If provided, renders a "Pick" button per row instead of "View". */
  onPick?: (entryId: string) => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function entryName(data: Record<string, unknown>, lang = "en"): string {
  const raw = data.name ?? ""
  if (typeof raw === "object" && raw !== null) {
    return (raw as Record<string, string>)[lang] ?? Object.values(raw as Record<string, string>)[0] ?? ""
  }
  return String(raw)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CatalogBrowser({ catalogType, onPick }: CatalogBrowserProps) {
  const [entries, setEntries] = useState<CatalogEntry[]>([])
  const [schema, setSchema] = useState<JsonSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewEntry, setViewEntry] = useState<CatalogEntry | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [data, schemaData] = await Promise.all([
        api.master.listCatalog(catalogType),
        api.master.getSchema(catalogType),
      ])
      setEntries(data)
      setSchema(schemaData)
    } catch {
      setError("Failed to load catalog")
    } finally {
      setLoading(false)
    }
  }, [catalogType])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <div className="py-2 text-xs text-destructive">{error}</div>
  }

  // Detail view
  if (viewEntry && schema) {
    const data = (viewEntry.data ?? viewEntry) as Record<string, unknown>
    return (
      <div className="space-y-2">
        <Button size="sm" variant="ghost" onClick={() => setViewEntry(null)}>
          &larr; Back
        </Button>
        <div className="rounded border border-border p-3">
          <h3 className="mb-2 text-sm font-medium">{entryName(data)}</h3>
          <SchemaForm
            schema={schema}
            onSubmit={() => {}}
            initialValues={data}
          />
        </div>
      </div>
    )
  }

  // Table view
  return (
    <div className="space-y-2">
      <div className="rounded border border-border text-xs">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-2 py-1 text-left font-medium">ID</th>
              <th className="px-2 py-1 text-left font-medium">Name</th>
              <th className="px-2 py-1 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const id = entry.id as string
              const data = (entry.data ?? entry) as Record<string, unknown>
              return (
                <tr key={id} className="border-b border-border/50 last:border-0">
                  <td className="px-2 py-1 font-mono">{id}</td>
                  <td className="px-2 py-1">{entryName(data)}</td>
                  <td className="px-2 py-1 text-right">
                    {onPick ? (
                      <Button size="xs" variant="ghost" onClick={() => onPick(id)}>
                        Pick
                      </Button>
                    ) : (
                      <Button size="xs" variant="ghost" onClick={() => setViewEntry(entry)}>
                        <Eye className="mr-1 h-3 w-3" />
                        View
                      </Button>
                    )}
                  </td>
                </tr>
              )
            })}
            {entries.length === 0 && (
              <tr>
                <td colSpan={3} className="px-2 py-3 text-center text-muted-foreground">
                  No entries
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
