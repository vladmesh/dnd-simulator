import { del, get, post, put } from "@/transport/requestCore"
import type { AdvanceTimeRequest, CreateSessionRequest, MessageResponse, SessionListItem, SessionResponse, SetLangRequest, WorldStateResponse } from "@/types/api"

export const masterSessionClient = {
  getSessions: () => get<SessionListItem[]>("/api/master/sessions"),
  createSession: (data: CreateSessionRequest) => post<SessionResponse>("/api/master/sessions", data),
  getSession: (sessionId: string) => get<WorldStateResponse>(`/api/master/sessions/${sessionId}`),
  deleteSession: (sessionId: string) => del<MessageResponse>(`/api/master/sessions/${sessionId}`),
  advanceTime: (sessionId: string, data: AdvanceTimeRequest) => post<MessageResponse>(`/api/master/sessions/${sessionId}/time/advance`, data),
  setLang: (sessionId: string, data: SetLangRequest) => put<MessageResponse>(`/api/master/sessions/${sessionId}/lang`, data),
  getSaves: (sessionId: string) => get<{ saves: string[] }>(`/api/master/sessions/${sessionId}/saves`),
  save: (sessionId: string, name?: string) => {
    const query = name ? `?name=${encodeURIComponent(name)}` : ""
    return post<MessageResponse>(`/api/master/sessions/${sessionId}/save${query}`)
  },
  loadSave: (sessionId: string, saveName: string) => post<MessageResponse>(`/api/master/sessions/${sessionId}/saves/${saveName}/load`),
  deleteSave: (sessionId: string, saveName: string) => del<MessageResponse>(`/api/master/sessions/${sessionId}/saves/${saveName}`),
}
