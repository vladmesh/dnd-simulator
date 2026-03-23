import { useState } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { WorldStateResponse } from "@/types/api"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Check, Loader2 } from "lucide-react"

interface Props {
  sessionId: string
  worldState: WorldStateResponse
}

export function WorldOverview({ sessionId, worldState }: Props) {
  return (
    <div className="space-y-8">
      <RegionsTable regions={worldState.regions} />
      <NationsTable sessionId={sessionId} nations={worldState.nations} />
      <SettlementsTable sessionId={sessionId} settlements={worldState.settlements} />
    </div>
  )
}

function RegionsTable({ regions }: { regions: Array<Record<string, unknown>> }) {
  const { t } = useTranslation(["master"])

  if (regions.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("master:no_regions")}</p>
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{t("master:regions")}</h2>
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_id")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_name")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_terrain")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_weather")}</th>
            </tr>
          </thead>
          <tbody>
            {regions.map((r) => (
              <tr key={String(r.id)} className="border-t border-border">
                <td className="px-3 py-2 font-mono text-xs">{String(r.id)}</td>
                <td className="px-3 py-2">{String(r.name)}</td>
                <td className="px-3 py-2">{String(r.terrain ?? "—")}</td>
                <td className="px-3 py-2">
                  {typeof r.weather === "object" && r.weather !== null
                    ? `${(r.weather as Record<string, unknown>).condition ?? "—"}, ${(r.weather as Record<string, unknown>).temperature ?? "?"}°`
                    : String(r.weather ?? "—")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function NationsTable({
  sessionId,
  nations,
}: {
  sessionId: string
  nations: Array<Record<string, unknown>>
}) {
  const { t } = useTranslation(["master"])
  const [editing, setEditing] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  if (nations.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("master:no_nations")}</p>
  }

  const startEdit = (nation: Record<string, unknown>) => {
    setEditing(String(nation.id))
    setValues({
      wealth: String(nation.wealth ?? 0),
      military: String(nation.military ?? 0),
      stability: String(nation.stability ?? 0),
    })
  }

  const saveEdit = (nationId: string) => {
    setSaving(true)
    api.master
      .patchNation(sessionId, nationId, {
        wealth: parseFloat(values.wealth),
        military: parseFloat(values.military),
        stability: parseFloat(values.stability),
      })
      .then(() => setEditing(null))
      .finally(() => setSaving(false))
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{t("master:nations")}</h2>
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_id")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_name")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_wealth")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_military")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_stability")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_actions")}</th>
            </tr>
          </thead>
          <tbody>
            {nations.map((n) => {
              const id = String(n.id)
              const isEditing = editing === id
              return (
                <tr key={id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">{id}</td>
                  <td className="px-3 py-2">{String(n.name)}</td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <Input
                        type="number"
                        step="0.1"
                        className="h-7 w-20"
                        value={values.wealth}
                        onChange={(e) => setValues({ ...values, wealth: e.target.value })}
                      />
                    ) : (
                      String(n.wealth ?? 0)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <Input
                        type="number"
                        step="0.1"
                        className="h-7 w-20"
                        value={values.military}
                        onChange={(e) => setValues({ ...values, military: e.target.value })}
                      />
                    ) : (
                      String(n.military ?? 0)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        className="h-7 w-20"
                        value={values.stability}
                        onChange={(e) => setValues({ ...values, stability: e.target.value })}
                      />
                    ) : (
                      String(n.stability ?? 0)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <div className="flex gap-1">
                        <Button size="xs" onClick={() => saveEdit(id)} disabled={saving}>
                          {saving ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                        </Button>
                        <Button size="xs" variant="ghost" onClick={() => setEditing(null)}>
                          ✕
                        </Button>
                      </div>
                    ) : (
                      <Button size="xs" variant="ghost" onClick={() => startEdit(n)}>
                        {t("master:edit")}
                      </Button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SettlementsTable({
  sessionId,
  settlements,
}: {
  sessionId: string
  settlements: Array<Record<string, unknown>>
}) {
  const { t } = useTranslation(["master"])
  const [editing, setEditing] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  if (settlements.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("master:no_settlements")}</p>
  }

  const startEdit = (s: Record<string, unknown>) => {
    setEditing(String(s.id))
    setValues({
      population: String(s.population ?? 0),
      prosperity: String(s.prosperity ?? 0),
      defenses: String(s.defenses ?? 0),
    })
  }

  const saveEdit = (settlementId: string) => {
    setSaving(true)
    api.master
      .patchSettlement(sessionId, settlementId, {
        population: parseInt(values.population),
        prosperity: parseFloat(values.prosperity),
        defenses: parseFloat(values.defenses),
      })
      .then(() => setEditing(null))
      .finally(() => setSaving(false))
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{t("master:settlements")}</h2>
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_id")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_name")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_region")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_population")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_prosperity")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_defenses")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("master:col_actions")}</th>
            </tr>
          </thead>
          <tbody>
            {settlements.map((s) => {
              const id = String(s.id)
              const isEditing = editing === id
              return (
                <tr key={id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">{id}</td>
                  <td className="px-3 py-2">{String(s.name)}</td>
                  <td className="px-3 py-2">{String(s.region_id ?? "—")}</td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <Input
                        type="number"
                        className="h-7 w-24"
                        value={values.population}
                        onChange={(e) => setValues({ ...values, population: e.target.value })}
                      />
                    ) : (
                      String(s.population ?? 0)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        className="h-7 w-20"
                        value={values.prosperity}
                        onChange={(e) => setValues({ ...values, prosperity: e.target.value })}
                      />
                    ) : (
                      String(s.prosperity ?? 0)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        className="h-7 w-20"
                        value={values.defenses}
                        onChange={(e) => setValues({ ...values, defenses: e.target.value })}
                      />
                    ) : (
                      String(s.defenses ?? 0)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <div className="flex gap-1">
                        <Button size="xs" onClick={() => saveEdit(id)} disabled={saving}>
                          {saving ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                        </Button>
                        <Button size="xs" variant="ghost" onClick={() => setEditing(null)}>
                          ✕
                        </Button>
                      </div>
                    ) : (
                      <Button size="xs" variant="ghost" onClick={() => startEdit(s)}>
                        {t("master:edit")}
                      </Button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
