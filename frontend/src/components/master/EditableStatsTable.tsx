import { useState } from "react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Check, Loader2 } from "lucide-react"

export interface ColumnDef<T> {
  /** Row field key (also the payload key for editable columns). */
  key: keyof T & string
  /** Translated header label. */
  label: string
  /** Read-only cell renderer; defaults to `String(row[key])`. */
  render?: (row: T) => ReactNode
  /** Editable numeric column: how to parse the input back to a number. */
  parse?: (raw: string) => number
  /** Extra `<input>` attributes for the edit control. */
  inputProps?: { step?: string; min?: string; max?: string }
  /** Tailwind width class for the edit control (default `w-20`). */
  width?: string
  /** Render the cell in a mono font (used for id columns). */
  mono?: boolean
}

interface EditableStatsTableProps<T extends { id: string }> {
  title: string
  columns: ColumnDef<T>[]
  rows: T[]
  emptyMessage: string
  /** When provided, editable columns become editable and an actions column is shown. */
  patch?: (id: string, values: Record<string, number>) => Promise<unknown>
}

/**
 * A stats table with optional per-row inline editing. Editable columns declare
 * a `parse`; on save the parsed values are sent through `patch`, with an
 * optimistic revert back to edit mode on failure.
 */
export function EditableStatsTable<T extends { id: string }>({
  title,
  columns,
  rows,
  emptyMessage,
  patch,
}: EditableStatsTableProps<T>) {
  const { t } = useTranslation(["master"])
  const [editing, setEditing] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const editableColumns = columns.filter((c) => c.parse)
  const canEdit = patch != null && editableColumns.length > 0

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>
  }

  const startEdit = (row: T) => {
    setEditing(row.id)
    const next: Record<string, string> = {}
    for (const col of editableColumns) {
      next[col.key] = String(row[col.key] ?? 0)
    }
    setValues(next)
  }

  const saveEdit = (row: T) => {
    if (!patch) return
    setSaving(true)
    const payload: Record<string, number> = {}
    for (const col of editableColumns) {
      payload[col.key] = col.parse!(values[col.key])
    }
    patch(row.id, payload)
      .then(() => setEditing(null))
      .catch(() => startEdit(row))
      .finally(() => setSaving(false))
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 text-left font-medium">
                  {col.label}
                </th>
              ))}
              {canEdit && (
                <th className="px-3 py-2 text-left font-medium">{t("master:col_actions")}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isEditing = editing === row.id
              return (
                <tr key={row.id} className="border-t border-border">
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-3 py-2${col.mono ? " font-mono text-xs" : ""}`}
                    >
                      {isEditing && col.parse ? (
                        <Input
                          type="number"
                          step={col.inputProps?.step}
                          min={col.inputProps?.min}
                          max={col.inputProps?.max}
                          className={`h-7 ${col.width ?? "w-20"}`}
                          value={values[col.key] ?? ""}
                          onChange={(e) =>
                            setValues({ ...values, [col.key]: e.target.value })
                          }
                        />
                      ) : col.render ? (
                        col.render(row)
                      ) : (
                        String(row[col.key] ?? "")
                      )}
                    </td>
                  ))}
                  {canEdit && (
                    <td className="px-3 py-2">
                      {isEditing ? (
                        <div className="flex gap-1">
                          <Button size="xs" onClick={() => saveEdit(row)} disabled={saving}>
                            {saving ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <Check className="size-3" />
                            )}
                          </Button>
                          <Button size="xs" variant="ghost" onClick={() => setEditing(null)}>
                            ✕
                          </Button>
                        </div>
                      ) : (
                        <Button size="xs" variant="ghost" onClick={() => startEdit(row)}>
                          {t("master:edit")}
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
