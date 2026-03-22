import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useGameStore } from "@/store/gameStore"
import { useAvailableActions } from "@/store/useAvailableActions"
import { wsClient } from "@/transport/wsClient"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

// Map action names to translation keys
const ACTION_LABELS: Record<string, string> = {
  idle: "game:look",
  wait: "game:wait_1h",
  end_turn: "game:end_turn",
  dodge: "game:dodge",
  flee: "game:flee",
  move: "game:move",
  dash: "game:dash",
}

export function ActionBar() {
  const { t } = useTranslation(["game", "common"])
  const isMyTurn = useGameStore((s) => s.isMyTurn)
  const waitingForAction = useGameStore((s) => s.waitingForAction)
  const budget = useGameStore((s) => s.budget)
  const actions = useAvailableActions()
  const [customCmd, setCustomCmd] = useState("")

  const sendAction = (name: string, params?: Record<string, unknown>) => {
    wsClient.send({ type: "action", name, params })
    useGameStore.getState().setWaitingForAction(true)
  }

  const sendCommand = (text: string) => {
    wsClient.send({ type: "command", text })
    useGameStore.getState().setWaitingForAction(true)
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

  return (
    <div className="border-t border-border px-4 py-2">
      {/* Budget display */}
      {budget && (
        <div className="mb-2 flex gap-3 text-xs text-muted-foreground">
          <span>{t("game:actions_label", { n: budget.actions })}</span>
          <span>{t("game:bonus_label", { n: budget.bonus_actions })}</span>
          <span>{t("game:movement_label", { n: budget.movement_remaining })}</span>
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
