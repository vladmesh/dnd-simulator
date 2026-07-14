import { del, get, patch, post, put } from "@/transport/requestCore"
import type { ActivationTriggerResponse, CreatureResponse, GiveItemRequest, MessageResponse, PatchCreatureRequest, PatchNationRequest, PatchSettlementRequest, SetActivationOverrideRequest, SetActivationTriggerRequest, SetBrainRequest, SetBrainResponse, SpawnCreatureRequest } from "@/types/api"

export const masterCreatureClient = {
  getCreatures: (sessionId: string, params?: { entity_type?: string; location_id?: string; active?: boolean }) => {
    const query = new URLSearchParams()
    if (params?.entity_type) query.set("entity_type", params.entity_type)
    if (params?.location_id) query.set("location_id", params.location_id)
    if (params?.active !== undefined) query.set("active", String(params.active))
    const qs = query.toString()
    return get<CreatureResponse[]>(`/api/master/sessions/${sessionId}/creatures${qs ? `?${qs}` : ""}`)
  },
  getCreature: (sessionId: string, entityId: string) => get<CreatureResponse>(`/api/master/sessions/${sessionId}/creatures/${entityId}`),
  spawnCreature: (sessionId: string, data: SpawnCreatureRequest) => post<CreatureResponse>(`/api/master/sessions/${sessionId}/creatures`, data),
  patchCreature: (sessionId: string, entityId: string, data: PatchCreatureRequest) => patch<MessageResponse>(`/api/master/sessions/${sessionId}/creatures/${entityId}`, data),
  deleteCreature: (sessionId: string, entityId: string) => del<MessageResponse>(`/api/master/sessions/${sessionId}/creatures/${entityId}`),
  setBrain: (sessionId: string, entityId: string, data: SetBrainRequest) => put<SetBrainResponse>(`/api/master/sessions/${sessionId}/creatures/${entityId}/brain`, data),
  setCreatureActivation: (sessionId: string, entityId: string, data: SetActivationOverrideRequest) => put<CreatureResponse>(`/api/master/sessions/${sessionId}/creatures/${entityId}/activation`, data),
  setActivationTrigger: (sessionId: string, entityId: string, triggerId: string, data: SetActivationTriggerRequest) => put<ActivationTriggerResponse>(`/api/master/sessions/${sessionId}/creatures/${entityId}/triggers/${encodeURIComponent(triggerId)}`, data),
  giveItem: (sessionId: string, entityId: string, data: GiveItemRequest) => post<{ item_id: string; name: string }>(`/api/master/sessions/${sessionId}/creatures/${entityId}/items`, data),
  patchNation: (sessionId: string, nationId: string, data: PatchNationRequest) => patch<MessageResponse>(`/api/master/sessions/${sessionId}/nations/${nationId}`, data),
  patchSettlement: (sessionId: string, settlementId: string, data: PatchSettlementRequest) => patch<MessageResponse>(`/api/master/sessions/${sessionId}/settlements/${settlementId}`, data),
}
