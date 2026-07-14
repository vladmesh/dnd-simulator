import { del, get, post, put } from "@/transport/requestCore"
import type {
  AssembleWorldRequest,
  CreateWorldRequest,
  EntityEntry,
  ForkWorldRequest,
  LayerFileResponse,
  LayerFilesResponse,
  MessageResponse,
  RefOption,
  TemplateListItem,
  UpdateLayerFileRequest,
  WorldListItem,
  WorldManifestResponse,
} from "@/types/api"

export const masterWorldClient = {
  getLibraryTemplates: (layerType: string, geography?: string) => {
    const query = geography ? `?geography=${encodeURIComponent(geography)}` : ""
    return get<TemplateListItem[]>(`/api/master/library/${layerType}${query}`)
  },
  assembleWorld: (data: AssembleWorldRequest) => post<WorldListItem>("/api/master/worlds/assemble", data),
  getWorlds: (lang?: string) => get<WorldListItem[]>(lang ? `/api/master/worlds?lang=${lang}` : "/api/master/worlds"),
  getWorld: (worldId: string) => get<Record<string, unknown>>(`/api/master/worlds/${worldId}`),
  getWorldManifest: (worldId: string, lang?: string) => {
    const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
    return get<WorldManifestResponse>(`/api/master/worlds/${worldId}/manifest${query}`)
  },
  forkLayer: (worldId: string, layerType: string) => post<MessageResponse>(`/api/master/worlds/${worldId}/fork/${layerType}`),
  getLayerFiles: (worldId: string, layerType: string) => get<LayerFilesResponse>(`/api/master/worlds/${worldId}/layers/${layerType}/files`),
  getLayerFile: (worldId: string, layerType: string, filename: string) => get<LayerFileResponse>(`/api/master/worlds/${worldId}/layers/${layerType}/files/${encodeURIComponent(filename)}`),
  updateLayerFile: (worldId: string, layerType: string, filename: string, data: UpdateLayerFileRequest) => put<MessageResponse>(`/api/master/worlds/${worldId}/layers/${layerType}/files/${encodeURIComponent(filename)}`, data),
  createWorld: (data: CreateWorldRequest) => post<WorldListItem>("/api/master/worlds", data),
  updateWorld: (worldId: string, data: CreateWorldRequest) => put<WorldListItem>(`/api/master/worlds/${worldId}`, data),
  forkWorld: (worldId: string, data: ForkWorldRequest) => post<WorldListItem>(`/api/master/worlds/${worldId}/fork`, data),
  deleteWorld: (worldId: string) => del<MessageResponse>(`/api/master/worlds/${worldId}`),
  getRefs: (worldId: string, refType: string) => get<RefOption[]>(`/api/master/worlds/${worldId}/refs/${refType}`),
  listEntities: (worldId: string, entityType: string) => get<EntityEntry[]>(`/api/master/worlds/${worldId}/entities/${entityType}`),
  getEntity: (worldId: string, entityType: string, entityId: string) => get<EntityEntry>(`/api/master/worlds/${worldId}/entities/${entityType}/${entityId}`),
  createEntity: (worldId: string, entityType: string, entityId: string, body: EntityEntry) => post<EntityEntry>(`/api/master/worlds/${worldId}/entities/${entityType}/${entityId}`, body),
  updateEntity: (worldId: string, entityType: string, entityId: string, body: EntityEntry) => put<EntityEntry>(`/api/master/worlds/${worldId}/entities/${entityType}/${entityId}`, body),
  deleteEntity: (worldId: string, entityType: string, entityId: string) => del<MessageResponse>(`/api/master/worlds/${worldId}/entities/${entityType}/${entityId}`),
}
