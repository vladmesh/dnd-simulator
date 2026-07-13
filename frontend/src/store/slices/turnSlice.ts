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
  ReactionMessage,
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

/** Game-time fields live only on peaceful awareness; combat awareness has none. */
export function extractGameTime(awareness: Awareness): GameTime | null {
  const a = awareness as PeacefulAwareness
  if ("hour" in a) {
    return { hour: a.hour, day: a.day, month: a.month, year: a.year }
  }
  return null
}

/** Initial (and reset) values for the turn-related state fields. */
export const turnSliceResetState: Pick<
  TurnSlice,
  | "mode"
  | "awareness"
  | "location"
  | "budget"
  | "gameTime"
  | "isMyTurn"
  | "waitingForAction"
  | "gameOver"
  | "lastError"
  | "reactionPrompt"
> = {
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
}

export const createTurnSlice: StateCreator<
  GameStore,
  [],
  [],
  TurnSlice
> = (set, get) => {
  // Shared handling for turn/action/round messages: player + events + the
  // mode/awareness/location/gameTime block. `extra` carries per-message fields.
  const applyCommon = (
    msg: TurnMessage | ActionResultMessage | RoundResultMessage,
    events: PerceivedEvent[],
    extra: Partial<TurnSlice>,
  ) => {
    get().updatePlayer(msg.player)
    get().appendEvents(events)
    const updates: Partial<TurnSlice> = {
      mode: msg.mode,
      awareness: msg.awareness,
      location: msg.location,
      ...extra,
    }
    const gameTime = extractGameTime(msg.awareness)
    if (gameTime) updates.gameTime = gameTime
    set(updates)
  }

  return {
    ...turnSliceResetState,

    onTurn: (msg) => {
      applyCommon(msg, msg.events, {
        budget: msg.budget ?? msg.awareness.turn_budget ?? null,
        isMyTurn: true,
        waitingForAction: false,
        lastError: null,
      })
    },

    onActionResult: (msg) => {
      const events = [...msg.events]
      if (msg.error) {
        events.push({ description: msg.error, event_type: "action_error" })
      }
      const extra: Partial<TurnSlice> = { waitingForAction: false }
      if (msg.budget != null) {
        extra.budget = msg.budget
      }
      applyCommon(msg, events, extra)
    },

    onRoundResult: (msg) => {
      applyCommon(msg, msg.events, { isMyTurn: false, waitingForAction: false })
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
      const message: ReactionMessage = { type: "reaction", name }
      if (params) {
        message.params = params
      }
      wsClient.send(message)
      set({ reactionPrompt: null })
    },

    setWaitingForAction: (waiting) => {
      set({ waitingForAction: waiting })
    },
  }
}
