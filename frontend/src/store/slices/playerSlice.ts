import type { StateCreator } from "zustand"
import type { PlayerStatus } from "@/types/game"
import type { GameStore } from "../gameStore"

export interface PlayerSlice {
  player: PlayerStatus | null
  updatePlayer: (status: PlayerStatus) => void
}

export const createPlayerSlice: StateCreator<
  GameStore,
  [],
  [],
  PlayerSlice
> = (set) => ({
  player: null,

  updatePlayer: (player: PlayerStatus) => {
    set({ player })
  },
})
