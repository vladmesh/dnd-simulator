import { create } from "zustand"
import {
  type ConnectionSlice,
  createConnectionSlice,
} from "./slices/connectionSlice"
import { type IdentitySlice, createIdentitySlice } from "./slices/identitySlice"
import { type PlayerSlice, createPlayerSlice } from "./slices/playerSlice"
import { type TurnSlice, createTurnSlice } from "./slices/turnSlice"
import { type LogSlice, createLogSlice } from "./slices/logSlice"

export type GameStore = ConnectionSlice &
  IdentitySlice &
  PlayerSlice &
  TurnSlice &
  LogSlice

export const useGameStore = create<GameStore>()((...a) => ({
  ...createConnectionSlice(...a),
  ...createIdentitySlice(...a),
  ...createPlayerSlice(...a),
  ...createTurnSlice(...a),
  ...createLogSlice(...a),
}))
