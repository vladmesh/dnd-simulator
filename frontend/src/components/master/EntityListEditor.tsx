import { useCallback, useEffect, useState } from "react"
import { api } from "@/transport/apiClient"
import type { EntityEntry, JsonSchema } from "@/types/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Loader2, Pencil, Plus, Trash2, X } from "lucide-react"
import { SchemaForm } from "./SchemaForm"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  worldId: string
  entityType: string
  readOnly: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract a human-readable name from an entity's data (supports localized name objects). */
function entityName(data: Record<string, unknown>, lang = "en"): string {
  const raw = data.name ?? data.id ?? ""
  if (typeof raw === "object" && raw !== null) {
    return (raw as Record<string, string>)[lang] ?? Object.values(raw as Record<string, string>)[0] ?? ""
  }
  return String(raw)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EntityListEditor({ worldId, entityType, readOnly }: Props) {
  const [entities, setEntities] = useState<EntityEntry[]>([])
  const [schema, setSchema] = useState<JsonSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Inline editor state: "create" | {entity} | null
  const [editing, setEditing] = useState<"create" | EntityEntry | null>(null)
  const [newId, setNewId] = useState("")

  // -----------------------------------------------------------------------
  // Data loading
  // -----------------------------------------------------------------------

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [entitiesData, schemaData] = await Promise.all([
        api.master.listEntities(worldId, entityType),
        api.master.getSchema(entityType),
      ])
      setEntities(entitiesData)
      setSchema(schemaData)
    } catch {
      setError("Failed to load entities")
    } finally {
      setLoading(false)
    }
  }, [worldId, entityType])

  useEffect(() => {
    load()
  }, [load])

  // -----------------------------------------------------------------------
  // CRUD handlers
  // -----------------------------------------------------------------------

  const openCreate = () => {
    setEditing("create")
    setNewId("")
  }

  const openEdit = (entity: EntityEntry) => {
    setEditing(entity)
  }

  const closeEditor = () => {
    setEditing(null)
  }

  const handleSave = async (data: Record<string, unknown>) => {
    try {
      if (editing === "create") {
        await api.master.createEntity(worldId, entityType, newId, data)
      } else if (editing) {
        await api.master.updateEntity(worldId, entityType, editing.id as string, data)
      }
      setEditing(null)
      await load()
    } catch (err) {
      setError(String(err))
    }
  }

  const handleDelete = async (entityId: string) => {
    if (!window.confirm(`Delete ${entityId}?`)) return
    try {
      await api.master.deleteEntity(worldId, entityType, entityId)
      await load()
    } catch (err) {
      setError(String(err))
    }
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error && entities.length === 0) {
    return <div className="py-2 text-xs text-destructive">{error}</div>
  }

  return (
    <div className="space-y-2">
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={openCreate}>
            <Plus className="mr-1 h-3 w-3" />
            Add
          </Button>
        </div>
      )}

      {/* Entity table */}
      <div className="rounded border border-border text-xs">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-2 py-1 text-left font-medium">ID</th>
              <th className="px-2 py-1 text-left font-medium">Name</th>
              {!readOnly && <th className="px-2 py-1 text-right font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {entities.map((entity) => {
              const id = entity.id as string
              const data = (entity.data ?? entity) as Record<string, unknown>
              return (
                <tr key={id} className="border-b border-border/50 last:border-0">
                  <td className="px-2 py-1 font-mono">{id}</td>
                  <td className="px-2 py-1">{entityName(data)}</td>
                  {!readOnly && (
                    <td className="px-2 py-1 text-right">
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => openEdit(entity)}
                      >
                        <Pencil className="mr-1 h-3 w-3" />
                        Edit
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => handleDelete(id)}
                      >
                        <Trash2 className="mr-1 h-3 w-3" />
                        Delete
                      </Button>
                    </td>
                  )}
                </tr>
              )
            })}
            {entities.length === 0 && (
              <tr>
                <td colSpan={readOnly ? 2 : 3} className="px-2 py-3 text-center text-muted-foreground">
                  No entities
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {error && <div className="text-xs text-destructive">{error}</div>}

      {/* Inline editor panel */}
      {editing && schema && (
        <div className="rounded border border-border bg-muted/30 p-3">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-medium">
              {editing === "create"
                ? `Add ${entityType}`
                : `Edit ${(editing as EntityEntry).id}`}
            </h3>
            <Button size="xs" variant="ghost" onClick={closeEditor}>
              <X className="h-3 w-3" />
            </Button>
          </div>
          <div className="space-y-3">
            {editing === "create" && (
              <div className="space-y-1">
                <Label htmlFor="entity-id">ID</Label>
                <Input
                  id="entity-id"
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                  placeholder="unique_id"
                />
              </div>
            )}
            <SchemaForm
              schema={schema}
              onSubmit={handleSave}
              initialValues={
                editing !== "create"
                  ? ((editing as EntityEntry).data as Record<string, unknown>)
                  : undefined
              }
              worldId={worldId}
              fetchRefs={api.master.getRefs}
            />
          </div>
        </div>
      )}
    </div>
  )
}
