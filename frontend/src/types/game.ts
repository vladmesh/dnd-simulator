// --- Enums ---

export type EventType =
  | "entity_died"
  | "entity_say"
  | "entity_attack"
  | "entity_dodge"
  | "entity_flee"
  | "entity_move"
  | "entity_dash"
  | "entity_disengage"
  | "entity_bless"
  | "entity_use_item"
  | "entity_second_wind"
  | "entity_equip"
  | "entity_unequip"
  | "entity_buy"
  | "entity_sell"
  | "action_error"
  | "turn_skipped"
  | "combat_started"
  | "combat_ended"
  | "encounter_spawned"
  | "weather_changed"
  | "time_advanced"
  | "squad_move"
  | "squad_combat"
  | "squad_materialized"
  | "squad_dematerialized"
  | "custom"

// --- Turn Budget ---

export interface TurnBudget {
  actions: number
  bonus_actions: number
  movement_remaining: number
  reaction: number
}

// --- Events ---

export interface PerceivedEvent {
  description: string
  event_type: EventType
  actor_id?: string | null
  target_id?: string | null
  data?: Record<string, unknown>
}

// --- Awareness ---

export interface NearbyEntity {
  id: string
  description: string
  is_wounded?: boolean
}

export interface CombatEntity {
  id: string
  description: string
  is_wounded?: boolean
  distance_ft?: number
  direction?: string
  conditions?: string[]
}

export interface ItemInfo {
  id: string
  name: string
  type?: string
  slot?: string
  description: string
  price?: number | null
}

export interface EquippedInfo {
  slot: string
  item_id: string
  name: string
  description: string
}

export interface ActionParamInfo {
  name: string
  type: string
  required: boolean
}

export interface CostOption {
  cost_type: string
  source: string
}

export interface ActionInfo {
  name: string
  description: string
  params: ActionParamInfo[]
  cost_options?: CostOption[]
}

export interface MerchantInfo {
  id: string
  name: string
  gold: number
  items: ItemInfo[]
}

export interface PeacefulAwareness {
  hour: number
  day: number
  month: number
  year: number
  weather: Record<string, unknown>
  location_name: string
  region_name: string
  settlements?: Array<Record<string, unknown>> | null
  territory_owner?: string | null
  nation_info?: Record<string, unknown> | null
  nearby: NearbyEntity[]
  turn_budget?: TurnBudget | null
  available_actions?: ActionInfo[]
  available_items?: ItemInfo[]
  merchants?: MerchantInfo[]
}

export interface CombatAwareness {
  self_hp: number
  self_max_hp: number
  self_ac: number
  self_speed: number
  self_weapon: string
  self_weapon_damage: string
  nearby: CombatEntity[]
  round_number: number
  walls?: string[]
  battle_map_ascii?: string
  turn_budget?: TurnBudget | null
  self_conditions?: string[]
  available_actions?: ActionInfo[]
  available_items?: ItemInfo[]
}

export type Awareness = PeacefulAwareness | CombatAwareness

export type GameMode = "peaceful" | "combat"

// --- Location ---

export interface LocationPath {
  target_id: string
  target_name: string
  distance_m: number
}

export interface LocationData {
  current_location: string
  current_location_id: string
  description: string
  region_id: string
  paths: LocationPath[]
}

// --- Player Status (WS) ---

export interface AbilityScores {
  str: number
  dex: number
  con: number
  int: number
  wis: number
  cha: number
}

export interface PlayerStatus {
  player_id: string
  name: string
  race: string
  char_class: string
  level: number
  alignment: string
  hp: number
  max_hp: number
  ac: number
  gold: number
  location_id: string
  ability_scores: AbilityScores
  equipped?: EquippedInfo[]
  inventory?: ItemInfo[]
}

// --- Actions ---

export type ActionName =
  | "idle"
  | "say"
  | "attack"
  | "dodge"
  | "flee"
  | "move"
  | "dash"
  | "end_turn"
  | "skip"
  | "wait"
  | "use_item"
  | "bless"
  | "equip"
  | "unequip"
  | "buy"
  | "sell"

export interface Action {
  name: ActionName
  params?: Record<string, unknown>
}
