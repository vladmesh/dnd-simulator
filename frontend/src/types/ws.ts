import type {
  Awareness,
  GameMode,
  LocationData,
  PerceivedEvent,
  PlayerStatus,
  ReactionOptionInfo,
  ReactionTriggerInfo,
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

export interface ReactionPromptMessage {
  type: "reaction_prompt"
  trigger: ReactionTriggerInfo
  options: ReactionOptionInfo[]
}

export type ServerMessage =
  | TurnMessage
  | ActionResultMessage
  | RoundResultMessage
  | ErrorMessage
  | GameOverMessage
  | ReactionPromptMessage

// --- Client → Server ---

export interface ActionMessage {
  type: "action"
  name: string
  params?: Record<string, unknown>
}

export interface ReactionMessage {
  type: "reaction"
  name: string
  params?: Record<string, unknown>
}

export type ClientMessage = ActionMessage | ReactionMessage
