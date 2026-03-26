// --- Request models ---

export interface CreateSessionRequest {
  world_name?: string
  lang?: string
}

export interface CreatePlayerRequest {
  name?: string
  race?: string
  char_class?: string
  level?: number
  alignment?: string
  appearance?: string
  hp?: number
  ac?: number
  gold?: number
  start_region?: string
  ability_scores?: Record<string, number> | null
  attacks?: Array<Record<string, unknown>> | null
}

export interface SpawnCreatureRequest {
  id: string
  name: string
  entity_type?: string
  region_id?: string
  start_location?: string
  hp?: number
  ac?: number
  speed?: number
  attacks?: Array<Record<string, unknown>> | null
  ability_scores?: Record<string, number> | null
  role?: string
  personality?: string
  settlement_id?: string
  ai?: string
}

export interface PatchCreatureRequest {
  current_hp?: number | null
  ac?: number | null
  location_id?: string | null
  conditions?: string[] | null
  gold?: number | null
  personality?: string | null
}

export interface SetBrainRequest {
  type: string
  model?: string
}

export interface PatchNationRequest {
  wealth?: number | null
  military?: number | null
  stability?: number | null
}

export interface PatchSettlementRequest {
  population?: number | null
  prosperity?: number | null
  defenses?: number | null
}

export interface CreateWorldRequest {
  id: string
  name: string
  description?: string
  regions?: Record<string, unknown>
  locations?: Record<string, unknown>
  nations?: Record<string, unknown>
  npcs?: Record<string, unknown>
}

export interface AssembleWorldRequest {
  id: string
  name: string
  description?: string
  layer_selections: Record<string, string>
  default_player_faction?: string
}

export interface AdvanceTimeRequest {
  hours?: number
}

export interface SetLangRequest {
  lang: string
}

export interface GiveItemRequest {
  name: string
  type: string // "potion", "weapon", "armor", "shield"
  price?: number | null
  // Potion fields
  heal_dice?: string | null
  // Weapon fields
  weapon_id?: string | null
  category?: string | null
  attack_name?: string | null
  damage?: Array<{ dice: string; type: string }> | null
  ability?: string | null
  reach?: number | null
  is_magic?: boolean | null
  is_finesse?: boolean | null
  grant_actions?: string[] | null
}

// --- Response models ---

export interface SessionResponse {
  session_id: string
  player_name: string
  player_location: string
  time: string
}

export interface WorldListItem {
  id: string
  name: string
  description: string
}

export interface PlayerStatusResponse {
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
  appearance: string
  ability_scores: Record<string, number>
}

export interface WorldStateResponse {
  session_id: string
  time: string
  regions: Array<Record<string, unknown>>
  nations: Array<Record<string, unknown>>
  settlements: Array<Record<string, unknown>>
  entities: Array<Record<string, unknown>>
}

export interface InventoryItem {
  id: string
  name: string
  item_type: string
}

export interface EquippedWeapon {
  weapon_id: string
  attack_name: string
  damage: string
}

export interface CreatureResponse {
  id: string
  name: string
  location_id: string
  active: boolean
  hp: number
  max_hp: number
  ac: number
  conditions?: string[]
  entity_type?: string
  race?: string
  char_class?: string
  level?: number
  gold?: number
  role?: string
  personality?: string
  ai_type?: string
  settlement_id?: string
  memory?: Record<string, unknown> | null
  inventory?: InventoryItem[]
  equipped_weapon?: EquippedWeapon | null
}

export interface TemplateListItem {
  slug: string
  name: string
  layer_type: string
  version: string
  description: string
  tags: string[]
  requires_geography: string[]
}

export interface MessageResponse {
  message: string
}

export interface SessionListItem {
  session_id: string
  player_name: string
  player_location: string
  time: string
  world_name: string
}
