import type { StateCreator } from "zustand"
import { wsClient } from "@/transport/wsClient"
import type { WsStatus } from "@/transport/wsClient"
import type { GameStore } from "../gameStore"

export interface ConnectionSlice {
  wsStatus: WsStatus
  sessionId: string | null
  playerId: string | null
  connect: (sessionId: string, playerId?: string) => void
  disconnect: () => void
}

export const createConnectionSlice: StateCreator<
  GameStore,
  [],
  [],
  ConnectionSlice
> = (set, get) => {
  // Subscribe to WS status changes — use setTimeout to avoid
  // useSyncExternalStore tearing during React commit phase
  wsClient.onStatus((wsStatus) => {
    setTimeout(() => set({ wsStatus }), 0)
  })

  // Subscribe to WS messages and dispatch to other slices
  wsClient.onMessage((msg) => {
    setTimeout(() => {
      const state = get()
      switch (msg.type) {
        case "turn":
          state.onTurn(msg)
          break
        case "action_result":
          state.onActionResult(msg)
          break
        case "round_result":
          state.onRoundResult(msg)
          break
        case "error":
          state.onError(msg)
          break
        case "game_over":
          state.onGameOver()
          break
      }
    }, 0)
  })

  return {
    wsStatus: "disconnected",
    sessionId: null,
    playerId: null,

    connect: (sessionId: string, playerId?: string) => {
      set({ sessionId, playerId: playerId ?? null })
      wsClient.connect(sessionId, playerId)
    },

    disconnect: () => {
      wsClient.disconnect()
      set({ sessionId: null, playerId: null })
    },
  }
}
