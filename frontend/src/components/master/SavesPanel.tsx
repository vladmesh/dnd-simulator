import { useEffect, useState, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api } from "@/transport/apiClient"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Loader2, Save, Download, Trash2 } from "lucide-react"

interface Props {
  sessionId: string
  onLoaded: () => void
}

export function SavesPanel({ sessionId, onLoaded }: Props) {
  const { t } = useTranslation(["master", "common"])
  const [saves, setSaves] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saveName, setSaveName] = useState("")
  const [saving, setSaving] = useState(false)
  const [operating, setOperating] = useState<string | null>(null)

  const refresh = useCallback(() => {
    api.master
      .getSaves(sessionId)
      .then((res) => setSaves(res.saves))
      .finally(() => setLoading(false))
  }, [sessionId])

  useEffect(() => { refresh() }, [refresh])

  const saveGame = () => {
    setSaving(true)
    api.master
      .save(sessionId, saveName || undefined)
      .then(() => { setSaveName(""); refresh(); toast.success(t("master:saved")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setSaving(false))
  }

  const loadSave = (name: string) => {
    if (!confirm(t("master:confirm_load_save", { name }))) return
    setOperating(name)
    api.master
      .loadSave(sessionId, name)
      .then(() => { refresh(); onLoaded(); toast.success(t("master:loaded")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setOperating(null))
  }

  const deleteSave = (name: string) => {
    if (!confirm(t("master:confirm_delete_save", { name }))) return
    setOperating(name)
    api.master
      .deleteSave(sessionId, name)
      .then(() => { refresh(); toast.success(t("master:save_deleted")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setOperating(null))
  }

  return (
    <div className="max-w-lg space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Save className="size-4" />
            {t("master:save_game")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Input
                placeholder={t("master:save_name")}
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
              />
            </div>
            <Button onClick={saveGame} disabled={saving}>
              {saving && <Loader2 className="mr-1 size-3 animate-spin" />}
              {t("master:save_game")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("master:saves")}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between rounded border border-border px-3 py-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-7 w-24" />
                </div>
              ))}
            </div>
          ) : saves.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("master:no_saves")}</p>
          ) : (
            <div className="space-y-2">
              {saves.map((name) => (
                <div key={name} className="flex items-center justify-between rounded border border-border px-3 py-2">
                  <span className="font-mono text-sm">{name}</span>
                  <div className="flex gap-1">
                    <Button
                      size="xs"
                      variant="secondary"
                      disabled={operating === name}
                      onClick={() => loadSave(name)}
                    >
                      {operating === name ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <Download className="mr-1 size-3" />
                      )}
                      {t("master:load_save")}
                    </Button>
                    <Button
                      size="xs"
                      variant="destructive"
                      disabled={operating === name}
                      onClick={() => deleteSave(name)}
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
