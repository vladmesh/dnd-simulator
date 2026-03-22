import { useEffect, useRef } from "react"
import { useParams } from "react-router"
import { useGameStore } from "@/store/gameStore"
import { Header } from "./Header"
import { EventLog } from "./EventLog"
import { ActionBar } from "./ActionBar"
import { Perception } from "./Perception"
import { LocationPanel } from "./LocationPanel"
import { PlayerStats } from "./PlayerStats"

export function GameScreen() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const lastError = useGameStore((s) => s.lastError)
  const gameOver = useGameStore((s) => s.gameOver)
  const connectedRef = useRef(false)

  useEffect(() => {
    if (!sessionId) return
    // Guard against StrictMode double-mount: only connect once
    if (!connectedRef.current) {
      connectedRef.current = true
      useGameStore.getState().connect(sessionId)
    }
    return () => {
      connectedRef.current = false
      useGameStore.getState().disconnect()
    }
  }, [sessionId])

  return (
    <div className="dark flex h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <Header />

      {/* Errors & Game Over */}
      {lastError && (
        <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-1.5 text-sm text-destructive">
          {lastError}
        </div>
      )}
      {gameOver && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-1.5 text-center text-sm font-bold text-red-500">
          GAME OVER
        </div>
      )}

      {/* Main area: EventLog + Sidebar */}
      <div className="flex min-h-0 flex-1">
        {/* Event log (main panel) */}
        <div className="flex flex-1 flex-col border-r border-border">
          <EventLog />
        </div>

        {/* Sidebar */}
        <div className="hidden w-72 flex-col gap-4 overflow-y-auto p-3 md:flex">
          <Perception />
          <div className="border-t border-border" />
          <LocationPanel />
          <div className="border-t border-border" />
          <PlayerStats />
        </div>
      </div>

      {/* Action bar */}
      <ActionBar />
    </div>
  )
}
