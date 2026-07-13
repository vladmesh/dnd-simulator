import type { LevelUpRequest, PlayerStatus } from "@/types/game"
import { get, post } from "@/transport/requestCore"
import type { CreatePlayerRequest, PlayerStatusResponse } from "@/types/api"

export const playerClient = {
  getSetupConfig: () => get<{ starting_gold: number; point_buy_budget: number }>("/api/player/setup-config"),
  createCharacter: (sessionId: string, data: CreatePlayerRequest) => post<PlayerStatusResponse>(`/api/player/sessions/${sessionId}/character`, data),
  getStatus: (sessionId: string) => get<PlayerStatusResponse>(`/api/player/sessions/${sessionId}/status`),
  levelUp: (sessionId: string, body: LevelUpRequest) => post<PlayerStatus>(`/api/player/sessions/${sessionId}/level-up`, body),
}
