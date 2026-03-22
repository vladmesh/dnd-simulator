import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/transport/apiClient"
import { wsClient } from "@/transport/wsClient"
import { useGameStore } from "@/store/gameStore"
import type { WorldListItem } from "@/types/api"

// Expose for console testing
declare global {
  interface Window {
    api: typeof api
    ws: typeof wsClient
    store: typeof useGameStore
  }
}
window.api = api
window.ws = wsClient
window.store = useGameStore

function App() {
  const [health, setHealth] = useState<string | null>(null)
  const [worlds, setWorlds] = useState<WorldListItem[]>([])
  const [sessionInput, setSessionInput] = useState("")
  const logEndRef = useRef<HTMLDivElement>(null)

  const wsStatus = useGameStore((s) => s.wsStatus)
  const sessionId = useGameStore((s) => s.sessionId)
  const player = useGameStore((s) => s.player)
  const mode = useGameStore((s) => s.mode)
  const budget = useGameStore((s) => s.budget)
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const log = useGameStore((s) => s.log)
  const lastError = useGameStore((s) => s.lastError)
  const gameOver = useGameStore((s) => s.gameOver)
  const connect = useGameStore((s) => s.connect)
  const disconnect = useGameStore((s) => s.disconnect)

  useEffect(() => {
    api.health()
      .then((data) => setHealth(data.status))
      .catch(() => setHealth("unreachable"))
    api.master.getWorlds()
      .then(setWorlds)
      .catch(() => {})
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [log])

  const handleConnect = () => {
    if (sessionInput.trim()) {
      connect(sessionInput.trim())
    }
  }

  const handleSendCommand = (cmd: string) => {
    wsClient.send({ type: "command", text: cmd })
    useGameStore.getState().setWaitingForAction(true)
  }

  const statusColor: Record<string, string> = {
    disconnected: "text-muted-foreground",
    connecting: "text-yellow-500",
    connected: "text-green-500",
    error: "text-red-500",
  }

  return (
    <div className="dark min-h-screen bg-background p-6 text-foreground">
      <h1 className="mb-4 text-2xl font-bold">D&D Simulator — Debug</h1>

      {/* Status bar */}
      <div className="mb-4 flex flex-wrap gap-4 text-sm">
        <span>Backend: {health ?? "..."}</span>
        <span className={statusColor[wsStatus]}>WS: {wsStatus}</span>
        {sessionId && <span>Session: {sessionId}</span>}
        {worlds.length > 0 && (
          <span>Worlds: {worlds.map((w) => w.id).join(", ")}</span>
        )}
      </div>

      {/* Connect / Disconnect */}
      <div className="mb-4 flex gap-2">
        <input
          className="rounded border border-border bg-secondary px-3 py-1 text-sm"
          placeholder="session_id"
          value={sessionInput}
          onChange={(e) => setSessionInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleConnect()}
        />
        <Button size="sm" onClick={handleConnect} disabled={wsStatus === "connected"}>
          Connect
        </Button>
        <Button size="sm" variant="outline" onClick={disconnect} disabled={wsStatus === "disconnected"}>
          Disconnect
        </Button>
      </div>

      {/* Player info */}
      {player && (
        <div className="mb-4 rounded border border-border p-3 text-sm">
          <strong>{player.name}</strong> — {player.race} {player.char_class} L{player.level}
          {" | "}HP: {player.hp}/{player.max_hp} | AC: {player.ac} | Gold: {player.gold}
          {" | "}Mode: {mode} | Turn: {isMyTurn ? "YES" : "no"}
          {budget && (
            <span> | Budget: A:{budget.actions} B:{budget.bonus_actions} M:{budget.movement_remaining}</span>
          )}
        </div>
      )}

      {/* Errors & Game Over */}
      {lastError && (
        <div className="mb-2 text-sm text-red-500">Error: {lastError}</div>
      )}
      {gameOver && (
        <div className="mb-2 text-sm font-bold text-red-500">GAME OVER</div>
      )}

      {/* Quick commands */}
      {isMyTurn && (
        <div className="mb-4 flex flex-wrap gap-2">
          {["look", "wait 1", "end_turn", "dodge", "flee"].map((cmd) => (
            <Button
              key={cmd}
              size="sm"
              variant="secondary"
              onClick={() => handleSendCommand(cmd)}
            >
              {cmd}
            </Button>
          ))}
          <input
            className="rounded border border-border bg-secondary px-3 py-1 text-sm"
            placeholder="custom command..."
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.currentTarget.value) {
                handleSendCommand(e.currentTarget.value)
                e.currentTarget.value = ""
              }
            }}
          />
        </div>
      )}

      {/* Event log */}
      <div className="max-h-96 overflow-y-auto rounded border border-border p-3 font-mono text-xs">
        {log.length === 0 && (
          <span className="text-muted-foreground">No events yet. Connect to a session to start.</span>
        )}
        {log.map((entry) => (
          <div key={entry.id} className="mb-1">
            <span className="text-muted-foreground">[{entry.event.event_type}]</span>{" "}
            {entry.event.description}
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}

export default App
