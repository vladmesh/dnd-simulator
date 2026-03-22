import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { useAvailableActions } from "@/store/useAvailableActions"
import { wsClient } from "@/transport/wsClient"
import { BudgetDisplay } from "./BudgetDisplay"
import { Button } from "@/components/ui/button"
import { Loader2, ChevronDown } from "lucide-react"
import type { CombatAwareness } from "@/types/game"

// Map action names to translation keys
const ACTION_LABELS: Record<string, string> = {
  idle: "game:look",
  wait: "game:wait_1h",
  end_turn: "game:end_turn",
  dodge: "game:dodge",
  flee: "game:flee",
  dash: "game:dash",
}

export function ActionBar() {
  const { t } = useTranslation(["game", "common"])
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const budget = useGameStore((s) => s.budget)
  const mode = useGameStore((s) => s.mode)
  const awareness = useGameStore((s) => s.awareness)
  const actions = useAvailableActions()
  const [customCmd, setCustomCmd] = useState("")
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)

  const sendAction = (name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
    setOpenDropdown(null)
  }

  const sendCommand = (text: string) => {
    wsClient.send({ type: "command", text })
    useGameStore.getState().setWaitingForAction(true)
    setOpenDropdown(null)
  }

  if (!isMyTurn) {
    return (
      <div className="flex items-center gap-2 border-t border-border px-4 py-2 text-sm text-muted-foreground">
        {waitingForAction && <Loader2 className="size-4 animate-spin" />}
        {t("common:waiting_for_turn")}
      </div>
    )
  }

  const actionLabel = (action: { name: string; label: string }) => {
    const key = ACTION_LABELS[action.name]
    return key ? t(key) : action.label
  }

  const isCombat = mode === "combat" && awareness && "self_hp" in awareness
  const combatAwareness = isCombat ? (awareness as CombatAwareness) : null
  const enemies = combatAwareness?.nearby ?? []

  // In combat, group actions differently: Attack dropdown, Move dropdown, standalone buttons
  if (isCombat) {
    const hasAction = (budget?.actions ?? 0) > 0
    const hasMovement = (budget?.movement_remaining ?? 0) > 0

    return (
      <div className="border-t border-border px-4 py-2">
        {/* Budget display */}
        {budget && (
          <div className="mb-2">
            <BudgetDisplay budget={budget} />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {/* Attack dropdown */}
          {enemies.length > 0 && (
            <div className="relative">
              <Button
                size="sm"
                variant="destructive"
                disabled={!hasAction || waitingForAction}
                onClick={() => {
                  if (enemies.length === 1) {
                    sendAction("attack", { target_id: enemies[0].id })
                  } else {
                    setOpenDropdown(openDropdown === "attack" ? null : "attack")
                  }
                }}
              >
                {t("game:attack")}
                {enemies.length > 1 && <ChevronDown className="ml-1 size-3" />}
              </Button>
              {openDropdown === "attack" && enemies.length > 1 && (
                <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[160px] rounded border border-border bg-popover p-1 shadow-md">
                  {enemies.map((e) => (
                    <button
                      key={e.id}
                      className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
                      onClick={() => sendAction("attack", { target_id: e.id })}
                    >
                      {t("game:attack_target", { target: e.id })}
                      {e.distance_ft != null && (
                        <span className="ml-1 text-muted-foreground">({e.distance_ft}ft)</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Move dropdown */}
          <div className="relative">
            <Button
              size="sm"
              variant="secondary"
              disabled={!hasMovement || waitingForAction}
              onClick={() => setOpenDropdown(openDropdown === "move" ? null : "move")}
            >
              {t("game:move")}
              <ChevronDown className="ml-1 size-3" />
            </Button>
            {openDropdown === "move" && (
              <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[180px] rounded border border-border bg-popover p-1 shadow-md">
                {enemies.map((e) => (
                  <div key={e.id} className="flex gap-1">
                    <button
                      className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                      onClick={() => sendCommand(`move toward ${e.id}`)}
                    >
                      {t("game:move_toward", { target: e.id })}
                    </button>
                    <button
                      className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                      onClick={() => sendCommand(`move away ${e.id}`)}
                    >
                      {t("game:move_away", { target: e.id })}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dash dropdown */}
          <div className="relative">
            <Button
              size="sm"
              variant="secondary"
              disabled={!hasAction || waitingForAction}
              onClick={() => setOpenDropdown(openDropdown === "dash" ? null : "dash")}
            >
              {t("game:dash")}
              <ChevronDown className="ml-1 size-3" />
            </Button>
            {openDropdown === "dash" && (
              <div className="absolute bottom-full left-0 z-10 mb-1 min-w-[180px] rounded border border-border bg-popover p-1 shadow-md">
                {enemies.map((e) => (
                  <div key={e.id} className="flex gap-1">
                    <button
                      className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                      onClick={() => sendCommand(`dash toward ${e.id}`)}
                    >
                      {t("game:dash_toward", { target: e.id })}
                    </button>
                    <button
                      className="flex-1 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                      onClick={() => sendCommand(`dash away ${e.id}`)}
                    >
                      {t("game:dash_away", { target: e.id })}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Standalone combat actions */}
          <Button
            size="sm"
            variant="secondary"
            disabled={!hasAction || waitingForAction}
            onClick={() => sendAction("dodge")}
          >
            {t("game:dodge")}
          </Button>

          <Button
            size="sm"
            variant="secondary"
            disabled={!hasAction || waitingForAction}
            onClick={() => sendAction("flee")}
          >
            {t("game:flee")}
          </Button>

          <Button
            size="sm"
            variant="outline"
            disabled={waitingForAction}
            onClick={() => sendAction("end_turn")}
          >
            {t("game:end_turn")}
          </Button>

          {/* Custom command input */}
          <input
            className="ml-auto h-8 w-48 rounded-lg border border-border bg-transparent px-2.5 text-sm placeholder:text-muted-foreground"
            placeholder={t("game:command_placeholder")}
            value={customCmd}
            onChange={(e) => setCustomCmd(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && customCmd.trim()) {
                sendCommand(customCmd.trim())
                setCustomCmd("")
              }
            }}
          />
        </div>
      </div>
    )
  }

  // Peaceful mode — original layout
  return (
    <div className="border-t border-border px-4 py-2">
      {/* Budget display */}
      {budget && (
        <div className="mb-2">
          <BudgetDisplay budget={budget} />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((action, i) => (
          <Button
            key={`${action.name}-${i}`}
            size="sm"
            variant={action.name === "end_turn" ? "outline" : "secondary"}
            disabled={action.disabled || waitingForAction}
            onClick={() => {
              if (action.name === "wait") {
                sendCommand("wait 1")
              } else if (action.params) {
                sendAction(action.name, action.params)
              } else {
                sendAction(action.name)
              }
            }}
          >
            {actionLabel(action)}
          </Button>
        ))}

        {/* Custom command input */}
        <input
          className="ml-auto h-8 w-48 rounded-lg border border-border bg-transparent px-2.5 text-sm placeholder:text-muted-foreground"
          placeholder={t("game:command_placeholder")}
          value={customCmd}
          onChange={(e) => setCustomCmd(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && customCmd.trim()) {
              sendCommand(customCmd.trim())
              setCustomCmd("")
            }
          }}
        />
      </div>
    </div>
  )
}
