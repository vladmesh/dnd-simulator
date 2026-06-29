import { useEffect, useState, useCallback } from "react"
import { useParams, Link } from "react-router"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { WorldStateResponse } from "@/types/api"
import { Button } from "@/components/ui/button"
import { WorldOverview } from "./WorldOverview"
import { CreatureList } from "./CreatureList"
import { SessionLiveFeed } from "./SessionLiveFeed"
import { TimeControl } from "./TimeControl"
import { SavesPanel } from "./SavesPanel"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft } from "lucide-react"
import { useGameStore } from "@/store/gameStore"

type Tab = "world" | "creatures" | "live" | "time" | "saves"

export function SessionView() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const { t } = useTranslation(["master", "common"])
  // Admin observes a live table read-only — hide every hot-control write surface.
  const observe = useGameStore((s) => s.role) === "admin"
  const [worldState, setWorldState] = useState<WorldStateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>("world")

  const refresh = useCallback(() => {
    if (!sessionId) return
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
    // Live event feed — read-only observation surface for DM and admin alike.
    { key: "live", label: t("master:tab_live") },
    // time-advance and saves are write controls — absent for observers.
    ...(observe
      ? []
      : [
          { key: "time" as Tab, label: t("master:tab_time") },
          { key: "saves" as Tab, label: t("master:tab_saves") },
        ]),
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
        {observe && (
          <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {t("master:observing")}
          </span>
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
            <WorldOverview sessionId={sessionId} worldState={worldState} observe={observe} />
          )}
          {tab === "creatures" && (
            <CreatureList sessionId={sessionId} observe={observe} />
          )}
          {tab === "live" && <SessionLiveFeed sessionId={sessionId} />}
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
