import type { StateCreator } from "zustand"
import type { PlayerStatus } from "@/types/game"
import type { GameStore } from "../gameStore"

export interface PlayerSlice {
  player: PlayerStatus | null
  levelUpDismissed: boolean
  updatePlayer: (status: PlayerStatus) => void
  setLevelUpDismissed: (value: boolean) => void
}

export const createPlayerSlice: StateCreator<
  GameStore,
  [],
  [],
  PlayerSlice
> = (set) => ({
  player: null,
  levelUpDismissed: false,

  updatePlayer: (player: PlayerStatus) => {
    set({ player })
  },

  setLevelUpDismissed: (value: boolean) => {
    set({ levelUpDismissed: value })
  },
})
