import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, useNavigate } from "react-router"
import { useGameStore } from "@/store/gameStore"
import type { CombatEntity } from "@/types/game"
import { Header } from "./Header"
import { EventLog } from "./EventLog"
import { ActionBar } from "./ActionBar"
import { Perception } from "./Perception"
import { PlayerStats } from "./PlayerStats"
import { LocationPanel } from "./LocationPanel"
import { TradePanel } from "./TradePanel"
import { BattleMap } from "./BattleMap"
import { CombatPanel } from "./CombatPanel"
import { NpcInspectModal } from "./NpcInspectModal"
import { LogOverlay } from "./LogOverlay"

export function GameScreen() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const lastError = useGameStore((s) => s.lastError)
  const gameOver = useGameStore((s) => s.gameOver)
  const wsStatus = useGameStore((s) => s.wsStatus)
  const playerName = useGameStore((s) => s.player?.name)
  const mode = useGameStore((s) => s.mode)
  const isCombat = mode === "combat"
  const [logExpanded, setLogExpanded] = useState(false)
  const [inspectEntity, setInspectEntity] = useState<CombatEntity | null>(null)
  const connectedRef = useRef(false)
  const navigate = useNavigate()

  const openLog = useCallback(() => setLogExpanded(true), [])
  const closeLog = useCallback(() => setLogExpanded(false), [])
  const handleEntityClick = useCallback((entity: CombatEntity) => setInspectEntity(entity), [])
  const closeInspect = useCallback(() => setInspectEntity(null), [])

  useEffect(() => {
    if (!sessionId) return
    // Guard against StrictMode double-mount: only connect once
    if (!connectedRef.current) {
      connectedRef.current = true
      const playerId = localStorage.getItem(`player_id:${sessionId}`) ?? undefined
      useGameStore.getState().connect(sessionId, playerId)
    }
    return () => {
      connectedRef.current = false
      useGameStore.getState().disconnect()
    }
  }, [sessionId])

  // Redirect to home if WS connection permanently failed (e.g. session not found)
  useEffect(() => {
    if (wsStatus === "error") {
      navigate("/", { replace: true })
    }
  }, [wsStatus, navigate])

  // Dynamic page title with character name
  useEffect(() => {
    document.title = playerName ? `${playerName} — D&D Simulator` : "D&D Simulator"
    return () => { document.title = "D&D Simulator" }
  }, [playerName])

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

      {/* Compact log strip — hidden when full log overlay is open */}
      {!logExpanded && <EventLog compact onExpand={openLog} />}

      {/* Dashboard panels — 3 columns, with overlay container */}
      <div className="relative min-h-0 flex-1">
        <div className="grid h-full grid-cols-1 gap-px border-b border-border bg-border lg:grid-cols-3">
          {/* Left column: Nearby+Trade (peaceful) or CombatPanel (combat) */}
          <div className="overflow-y-auto bg-background p-3">
            {isCombat ? (
              <CombatPanel />
            ) : (
              <>
                <Perception />
                <div className="my-3 border-t border-border" />
                <TradePanel />
              </>
            )}
          </div>

          {/* Center column: Character + Equipment */}
          <div className="overflow-y-auto bg-background p-3">
            <PlayerStats />
          </div>

          {/* Right column: BattleMap (combat) or Location (peaceful) */}
          <div className="overflow-y-auto bg-background p-3">
            {isCombat ? <BattleMap onEntityClick={handleEntityClick} /> : <LocationPanel />}
          </div>
        </div>

        {/* Log overlay — covers panel grid */}
        {logExpanded && <LogOverlay onClose={closeLog} />}
      </div>

      {/* Combat inspect modal — triggered from BattleMap entity clicks */}
      <NpcInspectModal
        entity={inspectEntity}
        open={inspectEntity !== null}
        onClose={closeInspect}
        isCombat={true}
      />

      {/* Action bar */}
      <ActionBar />
    </div>
  )
}
