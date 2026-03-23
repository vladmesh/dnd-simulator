import type { StateCreator } from "zustand"
import type {
  Awareness,
  GameMode,
  LocationData,
  PeacefulAwareness,
  TurnBudget,
} from "@/types/game"
import type {
  ActionResultMessage,
  ErrorMessage,
  RoundResultMessage,
  TurnMessage,
} from "@/types/ws"
import type { GameStore } from "../gameStore"

export interface GameTime {
  hour: number
  day: number
  month: number
  year: number
}

export interface TurnSlice {
  mode: GameMode
  awareness: Awareness | null
  location: LocationData | null
  budget: TurnBudget | null
  gameTime: GameTime | null
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
  gameTime: null,
  isMyTurn: false,
  waitingForAction: false,
  gameOver: false,
  lastError: null,

  onTurn: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    const updates: Partial<TurnSlice> = {
      mode: msg.mode,
      awareness: msg.awareness,
      location: msg.location,
      budget: msg.budget ?? msg.awareness.turn_budget ?? null,
      isMyTurn: true,
      waitingForAction: false,
      lastError: null,
    }
    // Extract time from peaceful awareness (combat doesn't include time fields)
    const a = msg.awareness as PeacefulAwareness
    if ("hour" in a) {
      updates.gameTime = { hour: a.hour, day: a.day, month: a.month, year: a.year }
    }
    set(updates)
  },

  onActionResult: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    const updates: Partial<TurnSlice> = {
      mode: msg.mode,
      awareness: msg.awareness,
      location: msg.location,
      waitingForAction: false,
    }
    if (msg.budget != null) {
      updates.budget = msg.budget
    }
    const a = msg.awareness as PeacefulAwareness
    if ("hour" in a) {
      updates.gameTime = { hour: a.hour, day: a.day, month: a.month, year: a.year }
    }
    set(updates)
  },

  onRoundResult: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    const updates: Partial<TurnSlice> = {
      mode: msg.mode,
      awareness: msg.awareness,
      location: msg.location,
      isMyTurn: false,
      waitingForAction: false,
    }
    const a = msg.awareness as PeacefulAwareness
    if ("hour" in a) {
      updates.gameTime = { hour: a.hour, day: a.day, month: a.month, year: a.year }
    }
    set(updates)
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
