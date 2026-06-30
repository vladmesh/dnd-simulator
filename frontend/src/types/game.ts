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
  | "entity_lay_on_hands"
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
  | "round_start"
  | "reputation_changed"
  | "custom"

// --- Turn Budget ---

export interface TurnBudget {
  actions: number
  bonus_actions: number
  movement_remaining: number
  reaction: number
}

// --- Dice / Roll Breakdown ---

export interface DieRollData {
  sides: number
  result: number
  original?: number | null  // pre-reroll value
}

export interface AttackRollData {
  natural: number
  d20: DieRollData
  d20_alt?: DieRollData | null
  components: Array<{ source: string; value: number; dice: string }>
  total: number
  advantage: boolean
  disadvantage: boolean
}

export interface DamageComponentData {
  source: string
  dice: string
  dice_detail?: DieRollData[]
  amount: number
  type: string
}

// --- Events ---

export interface PerceivedEvent {
  description: string
  event_type: EventType
  actor_id?: string | null
  actor_name?: string | null
  target_id?: string | null
  data?: Record<string, unknown>
}

// --- Awareness ---

export interface NearbyEntity {
  id: string
  description: string
  is_wounded?: boolean
  is_hostile?: boolean
  is_dead?: boolean
  name?: string
  race?: string
  role?: string
  faction_id?: string
  faction_name?: string
  npc_description?: string
  is_merchant?: boolean
  lootable?: boolean
  loot_items?: ItemInfo[]
  loot_gold?: number
}

export interface CombatEntity {
  id: string
  description: string
  is_wounded?: boolean
  is_hostile?: boolean
  distance_ft?: number
  direction?: string
  x?: number
  y?: number
  conditions?: string[]
}

export interface ItemInfo {
  id: string
  name: string
  item_type?: string
  type?: string  // deprecated alias, use item_type
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
  cost_type?: string
  params: ActionParamInfo[]
  cost_options?: CostOption[]
  target_mode?: string
  target_scope?: string
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

export interface ResourcePoolInfo {
  id: string
  max_uses: number
  current_uses: number
}

export interface CombatAwareness {
  self_hp: number
  self_max_hp: number
  self_ac: number
  self_speed: number
  self_weapon: string
  self_weapon_damage: string
  self_x?: number
  self_y?: number
  nearby: CombatEntity[]
  round_number: number
  walls?: string[]
  battle_map_ascii?: string
  battle_map_width?: number
  battle_map_height?: number
  battle_map_walls?: Array<{ x1: number; y1: number; x2: number; y2: number }>
  turn_budget?: TurnBudget | null
  self_conditions?: string[]
  available_actions?: ActionInfo[]
  available_items?: ItemInfo[]
  reachable?: number[][]
  is_disengaging?: boolean
  self_resource_pools?: ResourcePoolInfo[]
}

export type Awareness = PeacefulAwareness | CombatAwareness

// --- Reaction Prompt ---

export interface ReactionTriggerInfo {
  trigger_type: string
  source_creature_id: string
  data: Record<string, unknown>
}

export interface ReactionOptionInfo {
  action_type: string
  description: string
  params: Record<string, unknown>
}

export interface ReactionPrompt {
  trigger: ReactionTriggerInfo
  options: ReactionOptionInfo[]
}

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
  experience: number
  level_up_available: boolean
  xp_to_next_level: number
  alignment: string
  hp: number
  max_hp: number
  ac: number
  gold: number
  location_id: string
  ability_scores: AbilityScores
  equipped?: EquippedInfo[]
  inventory?: ItemInfo[]
  resource_pools?: ResourcePoolInfo[]
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

// --- Level-up ---

export interface LevelUpRequest {
  fighting_style?: string
}
