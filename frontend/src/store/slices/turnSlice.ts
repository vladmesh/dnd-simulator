import type { StateCreator } from "zustand"
import type {
  Awareness,
  GameMode,
  LocationData,
  PeacefulAwareness,
  PerceivedEvent,
  ReactionPrompt,
  TurnBudget,
} from "@/types/game"
import type {
  ActionResultMessage,
  ErrorMessage,
  ReactionPromptMessage,
  RoundResultMessage,
  TurnMessage,
} from "@/types/ws"
import { wsClient } from "@/transport/wsClient"
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
  reactionPrompt: ReactionPrompt | null
  onTurn: (msg: TurnMessage) => void
  onActionResult: (msg: ActionResultMessage) => void
  onRoundResult: (msg: RoundResultMessage) => void
  onError: (msg: ErrorMessage) => void
  onGameOver: () => void
  onReactionPrompt: (msg: ReactionPromptMessage) => void
  submitReaction: (name: string, params?: Record<string, unknown>) => void
  setWaitingForAction: (waiting: boolean) => void
}

export const createTurnSlice: StateCreator<
  GameStore,
  [],
  [],
  TurnSlice
> = (set, get) => {
  const clearDismissIfCombatEnded = (events: PerceivedEvent[]) => {
    if (events.some((e) => e.event_type === "combat_ended")) {
      get().setLevelUpDismissed(false)
    }
  }

  return {
  mode: "peaceful",
  awareness: null,
  location: null,
  budget: null,
  gameTime: null,
  isMyTurn: false,
  waitingForAction: false,
  gameOver: false,
  lastError: null,
  reactionPrompt: null,

  onTurn: (msg) => {
    get().updatePlayer(msg.player)
    get().appendEvents(msg.events)
    clearDismissIfCombatEnded(msg.events)
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
    const events = [...msg.events]
    if (msg.error) {
      events.push({ description: msg.error, event_type: "action_error" })
    }
    get().appendEvents(events)
    clearDismissIfCombatEnded(events)
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
    clearDismissIfCombatEnded(msg.events)
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

  onReactionPrompt: (msg) => {
    set({
      reactionPrompt: {
        trigger: msg.trigger,
        options: msg.options,
      },
    })
  },

  submitReaction: (name, params) => {
    const message: Record<string, unknown> = { type: "reaction", name }
    if (params) {
      message.params = params
    }
    wsClient.send(message as import("@/types/ws").ReactionMessage)
    set({ reactionPrompt: null })
  },

  setWaitingForAction: (waiting) => {
    set({ waitingForAction: waiting })
  },
  }
}
