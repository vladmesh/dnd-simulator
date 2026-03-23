import type {
  Awareness,
  GameMode,
  LocationData,
  PerceivedEvent,
  PlayerStatus,
  TurnBudget,
} from "./game"

// --- Server → Client ---

export interface TurnMessage {
  type: "turn"
  mode: GameMode
  awareness: Awareness
  events: PerceivedEvent[]
  budget?: TurnBudget | null
  player: PlayerStatus
  location: LocationData
}

export interface ActionResultMessage {
  type: "action_result"
  actor: string
  action: string
  mode: GameMode
  awareness: Awareness
  events: PerceivedEvent[]
  budget?: TurnBudget | null
  player: PlayerStatus
  location: LocationData
  error?: string
}

export interface RoundResultMessage {
  type: "round_result"
  mode: GameMode
  awareness: Awareness
  events: PerceivedEvent[]
  player: PlayerStatus
  location: LocationData
}

export interface ErrorMessage {
  type: "error"
  message: string
}

export interface GameOverMessage {
  type: "game_over"
}

export type ServerMessage =
  | TurnMessage
  | ActionResultMessage
  | RoundResultMessage
  | ErrorMessage
  | GameOverMessage

// --- Client → Server ---

export interface ActionMessage {
  type: "action"
  name: string
  params?: Record<string, unknown>
}

export interface CommandMessage {
  type: "command"
  text: string
}

export type ClientMessage = ActionMessage | CommandMessage
