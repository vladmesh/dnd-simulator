import { useMemo } from "react"
import { useGameStore } from "./gameStore"
import type { CombatAwareness, PeacefulAwareness } from "@/types/game"

export interface AvailableAction {
  name: string
  label: string
  disabled: boolean
  params?: Record<string, unknown>
}

function isCombatAwareness(
  awareness: PeacefulAwareness | CombatAwareness,
): awareness is CombatAwareness {
  return "self_hp" in awareness
}

export function useAvailableActions(): AvailableAction[] {
  const mode = useGameStore((s) => s.mode)
  const awareness = useGameStore((s) => s.awareness)
  const budget = useGameStore((s) => s.budget)
  const isMyTurn = useGameStore((s) => s.isMyTurn)

  return useMemo(() => {
    if (!isMyTurn || !awareness) return []

    const hasAction = (budget?.actions ?? 0) > 0
    const hasMovement = (budget?.movement_remaining ?? 0) > 0

    if (mode === "combat" && isCombatAwareness(awareness)) {
      const actions: AvailableAction[] = []

      // Attack targets
      for (const entity of awareness.nearby) {
        actions.push({
          name: "attack",
          label: `Attack ${entity.id}`,
          disabled: !hasAction,
          params: { target_id: entity.id },
        })
      }

      actions.push({
        name: "dodge",
        label: "Dodge",
        disabled: !hasAction,
      })

      actions.push({
        name: "flee",
        label: "Flee",
        disabled: !hasAction,
      })

      actions.push({
        name: "move",
        label: "Move",
        disabled: !hasMovement,
      })

      actions.push({
        name: "dash",
        label: "Dash",
        disabled: !hasAction,
      })

      actions.push({
        name: "end_turn",
        label: "End Turn",
        disabled: false,
      })

      return actions
    }

    // Peaceful mode — no end_turn (meaningful actions auto-end the turn),
    // talk targets are in the Perception panel with inline text input
    const actions: AvailableAction[] = [
      { name: "wait", label: "Wait 1h", disabled: false, params: { hours: 1 } },
    ]

    return actions
  }, [mode, awareness, budget, isMyTurn])
}
