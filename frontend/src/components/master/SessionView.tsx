import { useEffect, useState, useCallback } from "react"
import { useParams, Link } from "react-router"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { WorldStateResponse } from "@/types/api"
import { Button } from "@/components/ui/button"
import { WorldOverview } from "./WorldOverview"
import { CreatureList } from "./CreatureList"
import { TimeControl } from "./TimeControl"
import { SavesPanel } from "./SavesPanel"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft } from "lucide-react"

type Tab = "world" | "creatures" | "time" | "saves"

export function SessionView() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const { t } = useTranslation(["master", "common"])
  const [worldState, setWorldState] = useState<WorldStateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>("world")

  const refresh = useCallback(() => {
    if (!sessionId) return
    setLoading(true)
    api.master
      .getSession(sessionId)
      .then(setWorldState)
      .catch(() => setError(t("master:session_not_found")))
      .finally(() => setLoading(false))
  }, [sessionId, t])

  useEffect(() => { refresh() }, [refresh])

  // Auto-refresh every 5s
  useEffect(() => {
    const interval = setInterval(() => {
      if (!sessionId) return
      api.master.getSession(sessionId).then(setWorldState).catch(() => {})
    }, 5000)
    return () => clearInterval(interval)
  }, [sessionId])

  if (!sessionId) return null

  const tabs: { key: Tab; label: string }[] = [
    { key: "world", label: t("master:tab_world") },
    { key: "creatures", label: t("master:tab_creatures") },
    { key: "time", label: t("master:tab_time") },
    { key: "saves", label: t("master:tab_saves") },
  ]

  return (
    <div className="dark mx-auto min-h-screen max-w-5xl bg-background px-4 py-8 text-foreground">
      <div className="mb-6 flex items-center gap-4">
        <Link to="/master">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-1 size-4" />
            {t("master:back_to_sessions")}
          </Button>
        </Link>
        <h1 className="font-mono text-lg font-bold">{sessionId.slice(0, 8)}</h1>
        {worldState && (
          <span className="text-sm text-muted-foreground">{worldState.time}</span>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="mb-6 flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "border-b-2 border-primary text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && !worldState ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : (
        <>
          {tab === "world" && worldState && (
            <WorldOverview sessionId={sessionId} worldState={worldState} />
          )}
          {tab === "creatures" && (
            <CreatureList sessionId={sessionId} />
          )}
          {tab === "time" && (
            <TimeControl sessionId={sessionId} onAdvanced={refresh} />
          )}
          {tab === "saves" && (
            <SavesPanel sessionId={sessionId} onLoaded={refresh} />
          )}
        </>
      )}
    </div>
  )
}
