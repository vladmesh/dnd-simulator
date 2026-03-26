import type {
  AdvanceTimeRequest,
  AssembleWorldRequest,
  CreatePlayerRequest,
  CreateSessionRequest,
  CreateWorldRequest,
  CreatureResponse,
  GiveItemRequest,
  MessageResponse,
  PatchCreatureRequest,
  PatchNationRequest,
  PatchSettlementRequest,
  PlayerStatusResponse,
  SessionListItem,
  SessionResponse,
  SetBrainRequest,
  SetLangRequest,
  SpawnCreatureRequest,
  TemplateListItem,
  WorldListItem,
  WorldManifestResponse,
  WorldStateResponse,
} from "@/types/api"

class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.name = "ApiError"
    this.status = status
    this.body = body
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  }
  if (body !== undefined) {
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(path, opts)
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    let parsed: unknown = text
    try {
      parsed = JSON.parse(text)
    } catch {
      // keep as string
    }
    throw new ApiError(res.status, parsed)
  }
  return res.json() as Promise<T>
}

function get<T>(path: string) {
  return request<T>("GET", path)
}
function post<T>(path: string, body?: unknown) {
  return request<T>("POST", path, body)
}
function put<T>(path: string, body?: unknown) {
  return request<T>("PUT", path, body)
}
function patch<T>(path: string, body?: unknown) {
  return request<T>("PATCH", path, body)
}
function del<T>(path: string) {
  return request<T>("DELETE", path)
}

// --- Master API ---

const master = {
  // Library
  getLibraryTemplates: (layerType: string, geography?: string) => {
    const query = geography ? `?geography=${encodeURIComponent(geography)}` : ""
    return get<TemplateListItem[]>(`/api/master/library/${layerType}${query}`)
  },

  assembleWorld: (data: AssembleWorldRequest) =>
    post<WorldListItem>("/api/master/worlds/assemble", data),

  // Worlds
  getWorlds: (lang?: string) =>
    get<WorldListItem[]>(lang ? `/api/master/worlds?lang=${lang}` : "/api/master/worlds"),

  getWorld: (worldId: string) =>
    get<Record<string, unknown>>(`/api/master/worlds/${worldId}`),

  getWorldManifest: (worldId: string, lang?: string) => {
    const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
    return get<WorldManifestResponse>(`/api/master/worlds/${worldId}/manifest${query}`)
  },

  forkLayer: (worldId: string, layerType: string) =>
    post<MessageResponse>(`/api/master/worlds/${worldId}/fork/${layerType}`),

  createWorld: (data: CreateWorldRequest) =>
    post<WorldListItem>("/api/master/worlds", data),

  updateWorld: (worldId: string, data: CreateWorldRequest) =>
    put<WorldListItem>(`/api/master/worlds/${worldId}`, data),

  // Sessions
  getSessions: () => get<SessionListItem[]>("/api/master/sessions"),

  createSession: (data: CreateSessionRequest) =>
    post<SessionResponse>("/api/master/sessions", data),

  getSession: (sessionId: string) =>
    get<WorldStateResponse>(`/api/master/sessions/${sessionId}`),

  deleteSession: (sessionId: string) =>
    del<MessageResponse>(`/api/master/sessions/${sessionId}`),

  // Creatures
  getCreatures: (
    sessionId: string,
    params?: {
      entity_type?: string
      location_id?: string
      active?: boolean
    },
  ) => {
    const query = new URLSearchParams()
    if (params?.entity_type) query.set("entity_type", params.entity_type)
    if (params?.location_id) query.set("location_id", params.location_id)
    if (params?.active !== undefined)
      query.set("active", String(params.active))
    const qs = query.toString()
    return get<CreatureResponse[]>(
      `/api/master/sessions/${sessionId}/creatures${qs ? `?${qs}` : ""}`,
    )
  },

  getCreature: (sessionId: string, entityId: string) =>
    get<CreatureResponse>(
      `/api/master/sessions/${sessionId}/creatures/${entityId}`,
    ),

  spawnCreature: (sessionId: string, data: SpawnCreatureRequest) =>
    post<CreatureResponse>(
      `/api/master/sessions/${sessionId}/creatures`,
      data,
    ),

  patchCreature: (
    sessionId: string,
    entityId: string,
    data: PatchCreatureRequest,
  ) =>
    patch<MessageResponse>(
      `/api/master/sessions/${sessionId}/creatures/${entityId}`,
      data,
    ),

  deleteCreature: (sessionId: string, entityId: string) =>
    del<MessageResponse>(
      `/api/master/sessions/${sessionId}/creatures/${entityId}`,
    ),

  setBrain: (sessionId: string, entityId: string, data: SetBrainRequest) =>
    put<MessageResponse>(
      `/api/master/sessions/${sessionId}/creatures/${entityId}/brain`,
      data,
    ),

  giveItem: (sessionId: string, entityId: string, data: GiveItemRequest) =>
    post<{ item_id: string; name: string }>(
      `/api/master/sessions/${sessionId}/creatures/${entityId}/items`,
      data,
    ),

  // Nations / Settlements
  patchNation: (
    sessionId: string,
    nationId: string,
    data: PatchNationRequest,
  ) =>
    patch<MessageResponse>(
      `/api/master/sessions/${sessionId}/nations/${nationId}`,
      data,
    ),

  patchSettlement: (
    sessionId: string,
    settlementId: string,
    data: PatchSettlementRequest,
  ) =>
    patch<MessageResponse>(
      `/api/master/sessions/${sessionId}/settlements/${settlementId}`,
      data,
    ),

  // Time
  advanceTime: (sessionId: string, data: AdvanceTimeRequest) =>
    post<MessageResponse>(
      `/api/master/sessions/${sessionId}/time/advance`,
      data,
    ),

  // Language
  setLang: (sessionId: string, data: SetLangRequest) =>
    put<MessageResponse>(
      `/api/master/sessions/${sessionId}/lang`,
      data,
    ),

  // Saves
  getSaves: (sessionId: string) =>
    get<{ saves: string[] }>(`/api/master/sessions/${sessionId}/saves`),

  save: (sessionId: string, name?: string) => {
    const query = name ? `?name=${encodeURIComponent(name)}` : ""
    return post<MessageResponse>(
      `/api/master/sessions/${sessionId}/save${query}`,
    )
  },

  loadSave: (sessionId: string, saveName: string) =>
    post<MessageResponse>(
      `/api/master/sessions/${sessionId}/saves/${saveName}/load`,
    ),

  deleteSave: (sessionId: string, saveName: string) =>
    del<MessageResponse>(
      `/api/master/sessions/${sessionId}/saves/${saveName}`,
    ),
}

// --- Player API ---

const player = {
  createCharacter: (sessionId: string, data: CreatePlayerRequest) =>
    post<PlayerStatusResponse>(
      `/api/player/sessions/${sessionId}/character`,
      data,
    ),

  getStatus: (sessionId: string) =>
    get<PlayerStatusResponse>(`/api/player/sessions/${sessionId}/status`),
}

// --- Health ---

const health = () => get<{ status: string }>("/health")

export const api = { master, player, health }
export { ApiError }
