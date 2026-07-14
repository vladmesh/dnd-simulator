import { useState } from "react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { api } from "@/transport/apiClient"
import type { CreatureResponse, GmActivationOverride } from "@/types/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

interface Props {
  sessionId: string
  creature: CreatureResponse
  onChanged: () => Promise<void>
}

const modes: GmActivationOverride[] = ["active", "dormant", "automatic"]

export function ActivationControls({ sessionId, creature, onChanged }: Props) {
  const { t } = useTranslation(["master"])
  const [pending, setPending] = useState<string | null>(null)

  const setOverride = async (override: GmActivationOverride) => {
    setPending(`override:${override}`)
    try {
      await api.master.setCreatureActivation(sessionId, creature.id, { override })
      await onChanged()
    } catch {
      toast.error(t("master:activation_update_error", "Could not update creature activity."))
    } finally {
      setPending(null)
    }
  }

  const setTriggerArmed = async (triggerId: string, armed: boolean) => {
    setPending(`trigger:${triggerId}`)
    try {
      await api.master.setActivationTrigger(sessionId, creature.id, triggerId, { armed })
      await onChanged()
    } catch {
      toast.error(t("master:trigger_update_error", "Could not update activation trigger."))
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="min-w-64 space-y-2">
      <div className="flex flex-wrap items-center gap-1">
        <Badge variant={creature.active ? "default" : "outline"}>
          {creature.active
            ? t("master:activation_actual_active", "Actually active")
            : t("master:activation_actual_dormant", "Actually dormant")}
        </Badge>
        <Badge variant="secondary">
          {t("master:activation_manual_mode", {
            mode: t(`master:activation_mode_${creature.gm_activation_override}`),
            defaultValue: "Manual: {{mode}}",
          })}
        </Badge>
      </div>
      <div className="flex flex-wrap gap-1">
        {modes.map((mode) => (
          <Button
            key={mode}
            size="xs"
            variant={creature.gm_activation_override === mode ? "default" : "outline"}
            disabled={pending !== null || creature.gm_activation_override === mode}
            onClick={() => void setOverride(mode)}
          >
            {t(`master:activation_command_${mode}`)}
          </Button>
        ))}
      </div>
      {creature.activation_triggers.map((trigger) => (
        <div key={trigger.id} className="flex flex-wrap items-center gap-1 text-xs">
          <span className="font-mono">{trigger.id}</span>
          <Badge variant={trigger.armed ? "secondary" : "outline"}>
            {trigger.armed ? t("master:trigger_armed") : t("master:trigger_disarmed")}
          </Badge>
          <Badge variant={trigger.active ? "default" : "outline"}>
            {trigger.active ? t("master:trigger_active") : t("master:trigger_inactive")}
          </Badge>
          <Button
            size="xs"
            variant="outline"
            aria-label={t(
              trigger.armed ? "master:disarm_trigger" : "master:arm_trigger",
              { id: trigger.id },
            )}
            disabled={pending !== null}
            onClick={() => void setTriggerArmed(trigger.id, !trigger.armed)}
          >
            {trigger.armed ? t("master:disarm") : t("master:arm")}
          </Button>
        </div>
      ))}
    </div>
  )
}
