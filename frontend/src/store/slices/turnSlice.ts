import type { StateCreator } from "zustand"
import type {
  Awareness,
  GameMode,
  LocationData,
  TurnBudget,
} from "@/types/game"
import type {
  ActionResultMessage,
  ErrorMessage,
  RoundResultMessage,
  TurnMessage,
} from "@/types/ws"
import type { GameStore } from "../gameStore"

export interface TurnSlice {
  mode: GameMode
  awareness: Awareness | null
  location: LocationData | null
  budget: TurnBudget | null
  isMyTurn: boolean
  waitingForAction: boolean
  gameOver: boolean
  lastError: string | null

  onTurn: (msg: TurnMessage) => void
  onActionResult: (msg: ActionResultMessage) => void
  onRoundResult: (msg: RoundResultMessage) => void
  onError: (msg: ErrorMessage) => void
  onGameOver: () => void
  setWaitingForAction: (waiting: boolean) => void
}

export const createTurnSlice: StateCreator<
  GameStore,
  [],
  [],
  TurnSlice
> = (set, get) => ({
  mode: "peaceful",
  awareness: null,
  location: null,
  budget: null,
  isMyTurn: false,
  waitingForAction: false,
  gameOver: false,
  lastError: null,

  onTurn: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    set({
      mode: msg.mode,
      awareness: msg.awareness,
      location: msg.location,
      budget: msg.budget ?? msg.awareness.turn_budget ?? null,
      isMyTurn: true,
      waitingForAction: false,
      lastError: null,
    })
  },

  onActionResult: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    set({
      budget: msg.budget ?? null,
      waitingForAction: false,
    })
  },

  onRoundResult: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    set({
      isMyTurn: false,
      waitingForAction: false,
    })
  },

  onError: (msg) => {
    set({ lastError: msg.message, waitingForAction: false })
  },

  onGameOver: () => {
    set({ gameOver: true, isMyTurn: false })
  },

  setWaitingForAction: (waiting) => {
    set({ waitingForAction: waiting })
  },
})
