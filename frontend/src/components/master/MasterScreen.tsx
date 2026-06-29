import { useEffect, useState, useCallback } from "react"
import { Link } from "react-router"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api } from "@/transport/apiClient"
import type { SessionListItem, WorldListItem } from "@/types/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { LanguageToggle } from "@/components/setup/LanguageToggle"
import { Skeleton } from "@/components/ui/skeleton"
import { Loader2, Trash2, Settings, GitFork } from "lucide-react"
import { WorldEditor } from "./WorldEditor"
import { useGameStore } from "@/store/gameStore"

export function MasterScreen() {
  const { t, i18n } = useTranslation(["master", "common"])
  const role = useGameStore((s) => s.role)
  const userId = useGameStore((s) => s.userId)
  // Lens projection (projection-only, no backend enforcement):
  //   worldbuilder → own worlds, no live sessions
  //   dm           → own worlds + own sessions + hot-controls
  //   admin        → whole park, read-only (observation, no writes)
  //   else         → full god-mode screen (fallback for player/null)
  const isWorldbuilder = role === "worldbuilder"
  const isDm = role === "dm"
  const isAdmin = role === "admin"
  const scopedCreator = isWorldbuilder || isDm ? userId ?? undefined : undefined
  const showSessions = !isWorldbuilder
  // Admin observes the park without touching the fiction — strip every write affordance.
  const canWrite = !isAdmin

  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [worlds, setWorlds] = useState<WorldListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [selectedWorld, setSelectedWorld] = useState<string>("")
  const [deleting, setDeleting] = useState<string | null>(null)
  const [editingWorld, setEditingWorld] = useState<string | null>(null)
  const [forkingWorld, setForkingWorld] = useState<string | null>(null)
  const [forkId, setForkId] = useState("")
  const [forkSubmitting, setForkSubmitting] = useState(false)

  const refresh = useCallback(() => {
    Promise.all([
      api.master.getSessions(),
      api.master.getWorlds(i18n.language, scopedCreator),
    ])
      .then(([s, w]) => {
        setSessions(s)
        setWorlds(w)
        if (w.length > 0 && !selectedWorld) setSelectedWorld(w[0].id)
      })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setLoading(false))
  }, [i18n.language, t, selectedWorld, scopedCreator])

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

  const handleFork = (worldId: string) => {
    setForkingWorld(worldId)
    setForkId("")
  }

  const submitFork = () => {
    if (!forkingWorld || !forkId.trim()) return
    setForkSubmitting(true)
    api.master
      .forkWorld(forkingWorld, { new_id: forkId.trim() })
      .then(() => {
        toast.success(t("master:world_forked"))
        setForkingWorld(null)
        setForkId("")
        refresh()
      })
      .catch(() => toast.error(t("master:fork_world_error")))
      .finally(() => setForkSubmitting(false))
  }

  const deleteWorld = (worldId: string) => {
    if (!confirm(t("master:confirm_delete_world", { id: worldId }))) return
    setDeleting(worldId)
    api.master
      .deleteWorld(worldId)
      .then(() => { refresh(); toast.success(t("master:world_deleted")) })
      .catch(() => toast.error(t("common:error")))
      .finally(() => setDeleting(null))
  }

  const editingWorldData = editingWorld ? worlds.find((w) => w.id === editingWorld) : null
  // DM lens scopes the session list to its own sessions; other lenses see all.
  const visibleSessions = isDm && userId ? sessions.filter((s) => s.created_by === userId) : sessions

  return (
    <div className="dark mx-auto min-h-screen max-w-4xl bg-background px-4 py-8 text-foreground">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t("master:title")}</h1>
          {role && userId && (
            <p className="text-sm text-muted-foreground" data-testid="identity-line">
              {userId} · {t(`common:role_${role}`)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <Link to="/">
            <Button variant="outline" size="sm">{t("common:back")}</Button>
          </Link>
        </div>
      </div>

      <Tabs defaultValue="worlds">
        <TabsList>
          <TabsTrigger value="worlds">{t("master:tab_worlds")}</TabsTrigger>
          {showSessions && <TabsTrigger value="sessions">{t("master:tab_sessions")}</TabsTrigger>}
        </TabsList>

        {/* ── Worlds Tab ── */}
        <TabsContent value="worlds">
          {editingWorld ? (
            <WorldEditor
              worldId={editingWorld}
              readOnly={isAdmin || !editingWorldData?.editable}
              onClose={() => setEditingWorld(null)}
            />
          ) : loading ? (
            <div className="grid gap-4 pt-4 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader className="pb-2">
                    <Skeleton className="h-5 w-24" />
                    <Skeleton className="mt-1 h-4 w-48" />
                  </CardHeader>
                </Card>
              ))}
            </div>
          ) : worlds.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {t("master:no_worlds")}
            </div>
          ) : (
            <div className="grid gap-4 pt-4 sm:grid-cols-2">
              {worlds.map((w) => (
                <Card
                  key={w.id}
                  data-testid={`world-card-${w.id}`}
                  className="cursor-pointer transition-colors hover:bg-muted/50"
                  onClick={() => setEditingWorld(w.id)}
                >
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">{w.name}</CardTitle>
                    <CardDescription>{w.description || w.id}</CardDescription>
                  </CardHeader>
                  {canWrite && (
                    <CardContent className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => { e.stopPropagation(); handleFork(w.id) }}
                      >
                        <GitFork className="mr-1 size-3" />
                        {t("master:fork_world_btn")}
                      </Button>
                      {w.editable && (
                        <Button
                          size="sm"
                          variant="destructive"
                          disabled={deleting === w.id}
                          onClick={(e) => { e.stopPropagation(); deleteWorld(w.id) }}
                        >
                          {deleting === w.id ? (
                            <Loader2 className="size-3 animate-spin" />
                          ) : (
                            <Trash2 className="mr-1 size-3" />
                          )}
                          {t("master:delete_world_btn")}
                        </Button>
                      )}
                    </CardContent>
                  )}
                </Card>
              ))}

              {/* Fork dialog */}
              {forkingWorld && (
                <Card data-testid="fork-dialog" className="col-span-full border-primary">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">
                      {t("master:fork_world_title", { name: forkingWorld })}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex items-end gap-2">
                    <div className="flex-1">
                      <Label htmlFor="fork-id">{t("master:field_id")}</Label>
                      <Input
                        id="fork-id"
                        value={forkId}
                        onChange={(e) => setForkId(e.target.value)}
                        pattern="^[a-z0-9_]+$"
                        placeholder="my_world"
                      />
                    </div>
                    <Button
                      onClick={submitFork}
                      disabled={forkSubmitting || !forkId.trim()}
                    >
                      {forkSubmitting && <Loader2 className="mr-1 size-3 animate-spin" />}
                      {t("master:fork_world_btn")}
                    </Button>
                    <Button variant="outline" onClick={() => setForkingWorld(null)}>
                      {t("common:cancel")}
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        {/* ── Sessions Tab ── */}
        {showSessions && (
        <TabsContent value="sessions">
          {canWrite && (
          <div className="mb-6 flex items-center gap-2 pt-4">
            <Select value={selectedWorld} onValueChange={(v) => { if (v) setSelectedWorld(v) }}>
              <SelectTrigger className="w-48">
                <span className="flex flex-1 truncate text-left">
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
          )}

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
          ) : visibleSessions.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {t("master:no_sessions")}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {visibleSessions.map((s) => (
                <Card key={s.session_id}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base font-mono">{s.session_id.slice(0, 8)}</CardTitle>
                    <CardDescription>
                      {s.player_name || "—"}{s.time ? ` · ${s.time}` : ""}
                      {s.world_name && ` · ${s.world_name}`}
                      {s.created_by ? ` · ${s.created_by}` : ""}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex items-center gap-2">
                    <Link to={`/master/${s.session_id}`}>
                      <Button size="sm" variant="secondary">
                        <Settings className="mr-1 size-3" />
                        {t("master:manage")}
                      </Button>
                    </Link>
                    {canWrite && (
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
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
