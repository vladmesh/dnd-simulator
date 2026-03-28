import { useEffect, useState, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api } from "@/transport/apiClient"
import type { CreatureResponse } from "@/types/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { CreatureForm } from "./CreatureForm"
import { Skeleton } from "@/components/ui/skeleton"
import { Loader2, Plus, Trash2, Brain } from "lucide-react"

interface Props {
  sessionId: string
}

type Filter = "all" | "npc" | "monster"

export function CreatureList({ sessionId }: Props) {
  const { t } = useTranslation(["master"])
  const [creatures, setCreatures] = useState<CreatureResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>("all")
  const [showForm, setShowForm] = useState(false)
  const [editCreature, setEditCreature] = useState<CreatureResponse | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setLoading(true)
    const params = filter === "all" ? undefined : { entity_type: filter }
    api.master
      .getCreatures(sessionId, params)
      .then(setCreatures)
      .finally(() => setLoading(false))
  }, [sessionId, filter])

  useEffect(() => { refresh() }, [refresh])

  const deleteCreature = (c: CreatureResponse) => {
    if (!confirm(t("master:confirm_delete_creature", { name: c.name }))) return
    setDeleting(c.id)
    api.master
      .deleteCreature(sessionId, c.id)
      .then(() => { refresh(); toast.success(t("master:delete_creature")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setDeleting(null))
  }

  const toggleBrain = (c: CreatureResponse) => {
    const newType = c.ai_type === "llm" ? "rule_based" : "llm"
    api.master
      .setBrain(sessionId, c.id, { type: newType })
      .then((res) => {
        refresh()
        if (res.warning) {
          toast.warning(t("master:no_llm_key", "No LLM key configured"))
        } else {
          toast.success(t("master:set_brain"))
        }
      })
      .catch(() => toast.error(t("common:error")))
  }

  const filterButtons: { key: Filter; label: string }[] = [
    { key: "all", label: t("master:filter_all") },
    { key: "npc", label: t("master:filter_npc") },
    { key: "monster", label: t("master:filter_monster") },
  ]

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex gap-1">
          {filterButtons.map((f) => (
            <Button
              key={f.key}
              size="sm"
              variant={filter === f.key ? "default" : "outline"}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </Button>
          ))}
        </div>
        <Button size="sm" onClick={() => { setEditCreature(null); setShowForm(true) }}>
          <Plus className="mr-1 size-3" />
          {t("master:spawn_creature")}
        </Button>
      </div>

      {loading ? (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                {[t("master:col_name"), t("master:col_type"), t("master:col_hp"), t("master:col_ac"), t("master:col_location"), t("master:col_ai"), t("master:col_active"), t("master:col_actions")].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-t border-border">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-3 py-2"><Skeleton className="h-4 w-16" /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : creatures.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">{t("master:no_creatures")}</p>
      ) : (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_name")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_type")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_hp")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_ac")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_location")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_ai")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_active")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("master:col_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {creatures.map((c) => (
                <tr key={c.id} className="border-t border-border">
                  <td className="px-3 py-2">
                    <button
                      className="text-left hover:underline"
                      onClick={() => { setEditCreature(c); setShowForm(true) }}
                    >
                      {c.name}
                    </button>
                    <span className="ml-1 font-mono text-xs text-muted-foreground">{c.id}</span>
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={c.entity_type === "monster" ? "destructive" : "secondary"}>
                      {c.entity_type || "npc"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2">
                    <span className={c.hp < c.max_hp ? "text-yellow-400" : ""}>
                      {c.hp}/{c.max_hp}
                    </span>
                  </td>
                  <td className="px-3 py-2">{c.ac}</td>
                  <td className="px-3 py-2 font-mono text-xs">{c.location_id}</td>
                  <td className="px-3 py-2">
                    <button
                      className="flex items-center gap-1 hover:underline"
                      onClick={() => toggleBrain(c)}
                      title={t("master:set_brain")}
                    >
                      <Brain className="size-3" />
                      {c.ai_type || "rule_based"}
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={c.active ? "default" : "outline"}>
                      {c.active ? "yes" : "no"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2">
                    <Button
                      size="xs"
                      variant="destructive"
                      disabled={deleting === c.id}
                      onClick={() => deleteCreature(c)}
                    >
                      {deleting === c.id ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <Trash2 className="size-3" />
                      )}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <CreatureForm
          sessionId={sessionId}
          creature={editCreature}
          onClose={() => { setShowForm(false); setEditCreature(null) }}
          onSaved={() => { setShowForm(false); setEditCreature(null); refresh() }}
        />
      )}
    </div>
  )
}
