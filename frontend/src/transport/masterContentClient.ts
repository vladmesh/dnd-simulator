import { del, get, post, put } from "@/transport/requestCore"
import type { CatalogEntry, JsonSchema, MessageResponse, SchemaInfo } from "@/types/api"

export const masterContentClient = {
  getSchemas: () => get<SchemaInfo[]>("/api/master/schemas"),
  getSchema: (entityType: string) => get<JsonSchema>(`/api/master/schemas/${entityType}`),
  listCatalog: (catalogType: string) => get<CatalogEntry[]>(`/api/master/catalogs/${catalogType}`),
  getCatalogEntry: (catalogType: string, entryId: string) => get<CatalogEntry>(`/api/master/catalogs/${catalogType}/${entryId}`),
  createCatalogEntry: (catalogType: string, entryId: string, body: CatalogEntry) => post<CatalogEntry>(`/api/master/catalogs/${catalogType}/${entryId}`, body),
  updateCatalogEntry: (catalogType: string, entryId: string, body: CatalogEntry) => put<CatalogEntry>(`/api/master/catalogs/${catalogType}/${entryId}`, body),
  deleteCatalogEntry: (catalogType: string, entryId: string) => del<MessageResponse>(`/api/master/catalogs/${catalogType}/${entryId}`),
}
