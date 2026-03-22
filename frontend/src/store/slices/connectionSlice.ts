import type { StateCreator } from "zustand"
import { wsClient } from "@/transport/wsClient"
import type { WsStatus } from "@/transport/wsClient"
import type { GameStore } from "../gameStore"

export interface ConnectionSlice {
  wsStatus: WsStatus
  sessionId: string | null
  connect: (sessionId: string) => void
  disconnect: () => void
}

export const createConnectionSlice: StateCreator<
  GameStore,
  [],
  [],
  ConnectionSlice
> = (set, get) => {
  // Subscribe to WS status changes
  wsClient.onStatus((wsStatus) => {
    set({ wsStatus })
  })

  // Subscribe to WS messages and dispatch to other slices
  wsClient.onMessage((msg) => {
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
  })

  return {
    wsStatus: "disconnected",
    sessionId: null,

    connect: (sessionId: string) => {
      set({ sessionId })
      wsClient.connect(sessionId)
    },

    disconnect: () => {
      wsClient.disconnect()
      set({ sessionId: null })
    },
  }
}
