import { useEffect, useState, useCallback } from "react"
import { Link } from "react-router"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api } from "@/transport/apiClient"
import type { SessionListItem, WorldListItem } from "@/types/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select"
import { LanguageToggle } from "@/components/setup/LanguageToggle"
import { Skeleton } from "@/components/ui/skeleton"
import { Loader2, Trash2, Settings } from "lucide-react"
import { WorldInspector } from "@/components/setup/WorldInspector"

export function MasterScreen() {
  const { t, i18n } = useTranslation(["master", "common"])
  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [worlds, setWorlds] = useState<WorldListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [selectedWorld, setSelectedWorld] = useState<string>("")
  const [deleting, setDeleting] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setLoading(true)
    Promise.all([
      api.master.getSessions(),
      api.master.getWorlds(i18n.language),
    ])
      .then(([s, w]) => {
        setSessions(s)
        setWorlds(w)
        if (w.length > 0 && !selectedWorld) setSelectedWorld(w[0].id)
      })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setLoading(false))
  }, [i18n.language, t, selectedWorld])

  useEffect(() => { refresh() }, [refresh])

  const createSession = () => {
    if (!selectedWorld) return
    setCreating(true)
    api.master
      .createSession({ world_name: selectedWorld, lang: i18n.language })
      .then(() => { refresh(); toast.success(t("master:new_session")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setCreating(false))
  }

  const deleteSession = (id: string) => {
    if (!confirm(t("master:confirm_delete_session", { id }))) return
    setDeleting(id)
    api.master
      .deleteSession(id)
      .then(() => { refresh(); toast.success(t("master:session_deleted")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setDeleting(null))
  }

  return (
    <div className="dark mx-auto min-h-screen max-w-4xl bg-background px-4 py-8 text-foreground">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("master:title")}</h1>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <Link to="/">
            <Button variant="outline" size="sm">{t("common:back")}</Button>
          </Link>
        </div>
      </div>

      <div className="mb-6 flex items-center gap-2">
        <Select value={selectedWorld} onValueChange={(v) => { if (v) setSelectedWorld(v) }}>
          <SelectTrigger className="w-48">
            <span className="flex flex-1 text-left truncate">
              {worlds.find((w) => w.id === selectedWorld)?.name ?? selectedWorld}
            </span>
          </SelectTrigger>
          <SelectContent>
            {worlds.map((w) => (
              <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={createSession} disabled={creating || !selectedWorld}>
          {creating && <Loader2 className="mr-1 size-3 animate-spin" />}
          {t("master:new_session")}
        </Button>
      </div>

      {selectedWorld && <WorldInspector worldId={selectedWorld} />}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="mt-1 h-4 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-28" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : sessions.filter((s) => !selectedWorld || s.world_name === selectedWorld).length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          {t("master:no_sessions")}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {sessions.filter((s) => !selectedWorld || s.world_name === selectedWorld).map((s) => (
            <Card key={s.session_id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-mono">{s.session_id.slice(0, 8)}</CardTitle>
                <CardDescription>
                  {s.player_name || "—"}{s.time ? ` · ${s.time}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-2">
                <Link to={`/master/${s.session_id}`}>
                  <Button size="sm" variant="secondary">
                    <Settings className="mr-1 size-3" />
                    {t("master:manage")}
                  </Button>
                </Link>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={deleting === s.session_id}
                  onClick={() => deleteSession(s.session_id)}
                >
                  {deleting === s.session_id ? (
                    <Loader2 className="size-3 animate-spin" />
                  ) : (
                    <Trash2 className="size-3" />
                  )}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
