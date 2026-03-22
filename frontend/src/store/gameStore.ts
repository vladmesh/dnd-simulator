import { create } from "zustand"
import {
  type ConnectionSlice,
  createConnectionSlice,
} from "./slices/connectionSlice"
import { type PlayerSlice, createPlayerSlice } from "./slices/playerSlice"
import { type TurnSlice, createTurnSlice } from "./slices/turnSlice"
import { type LogSlice, createLogSlice } from "./slices/logSlice"

export type GameStore = ConnectionSlice & PlayerSlice & TurnSlice & LogSlice

export const useGameStore = create<GameStore>()((...a) => ({
  ...createConnectionSlice(...a),
  ...createPlayerSlice(...a),
  ...createTurnSlice(...a),
  ...createLogSlice(...a),
}))
