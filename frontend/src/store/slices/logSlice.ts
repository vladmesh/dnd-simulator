import type { StateCreator } from "zustand"
import type { PerceivedEvent } from "@/types/game"
import type { GameStore } from "../gameStore"

const MAX_EVENTS = 200

export interface LogEntry {
  id: number
  event: PerceivedEvent
}

export interface LogSlice {
  log: LogEntry[]
  appendEvents: (events: PerceivedEvent[]) => void
  clearLog: () => void
}

let nextId = 1

export const createLogSlice: StateCreator<
  GameStore,
  [],
  [],
  LogSlice
> = (set) => ({
  log: [],

  appendEvents: (events) => {
    if (events.length === 0) return
    set((state) => {
      const newEntries = events.map((event) => ({
        id: nextId++,
        event,
      }))
      const combined = [...state.log, ...newEntries]
      return { log: combined.slice(-MAX_EVENTS) }
    })
  },

  clearLog: () => {
    set({ log: [] })
  },
})
