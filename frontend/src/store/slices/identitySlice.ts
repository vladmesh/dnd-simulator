import type { StateCreator } from "zustand"
import type { GameStore } from "../gameStore"

export type Role = "worldbuilder" | "dm" | "admin" | "player"

export const ROLES: Role[] = ["worldbuilder", "dm", "admin", "player"]

const STORAGE_KEY = "identity"

export interface PersistedIdentity {
  userId: string | null
  role: Role | null
}

/** Read the persisted identity from localStorage (the rehydrate path on reload). */
export function loadIdentity(): PersistedIdentity {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { userId: null, role: null }
    const parsed = JSON.parse(raw) as Partial<PersistedIdentity>
    return {
      userId: typeof parsed.userId === "string" ? parsed.userId : null,
      role: ROLES.includes(parsed.role as Role) ? (parsed.role as Role) : null,
    }
  } catch {
    return { userId: null, role: null }
  }
}

function persistIdentity(value: PersistedIdentity): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {
    // ignore persistence errors (private mode, quota, etc.)
  }
}

export interface IdentitySlice {
  userId: string | null
  role: Role | null
  setIdentity: (userId: string, role: Role) => void
}

export const createIdentitySlice: StateCreator<
  GameStore,
  [],
  [],
  IdentitySlice
> = (set) => {
  const initial = loadIdentity()
  return {
    userId: initial.userId,
    role: initial.role,

    setIdentity: (userId: string, role: Role) => {
      const next: PersistedIdentity = { userId, role }
      persistIdentity(next)
      set(next)
    },
  }
}
