import { useState } from "react"
import { useTranslation } from "react-i18next"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import type { PlayerStatus, LevelUpRequest } from "@/types/game"
import { api } from "@/transport/apiClient"

type CharClass = "fighter" | "paladin" | "rogue"

const FIGHTING_STYLES = ["defense", "dueling", "great_weapon_fighting"] as const
type FightingStyle = (typeof FIGHTING_STYLES)[number]

const HIT_DIE_AVG: Record<CharClass, number> = {
  fighter: 6,
  paladin: 6,
  rogue: 5,
}

interface LevelUpModalProps {
  open: boolean
  player: PlayerStatus
  sessionId?: string
  onClose: () => void
  onSuccess: (updated: PlayerStatus) => void
}

export function LevelUpModal({
  open,
  player,
  sessionId,
  onClose,
  onSuccess,
}: LevelUpModalProps) {
  const { t } = useTranslation("game")
  const [style, setStyle] = useState<FightingStyle | "">("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const charClass = player.char_class as CharClass
  const nextLevel = player.level + 1
  const conMod = Math.floor((player.ability_scores.con - 10) / 2)
  const hpDelta = Math.max((HIT_DIE_AVG[charClass] ?? 0) + conMod, 1)

  const needsFightingStyle = charClass === "paladin"
  const canConfirm = !submitting && (!needsFightingStyle || style !== "")

  async function handleConfirm() {
    if (!sessionId) return
    const body: LevelUpRequest = {}
    if (needsFightingStyle && style !== "") {
      body.fighting_style = style
    }
    setSubmitting(true)
    setError(null)
    try {
      const updated = await api.player.levelUp(sessionId, body)
      onSuccess(updated)
    } catch {
      setError(t("game:levelup_error_generic"))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md" data-testid="level-up-modal">
        <DialogHeader>
          <DialogTitle>{t("game:levelup_title", { level: nextLevel })}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-3 text-sm">
          <div className="text-muted-foreground">
            {t("game:levelup_current_to_next", {
              current: player.level,
              next: nextLevel,
            })}
          </div>

          <div data-testid="hp-gain">
            {t("game:levelup_hp_gain", { delta: hpDelta })}
          </div>

          {charClass === "fighter" && (
            <div>{t("game:levelup_fighter_action_surge")}</div>
          )}
          {charClass === "rogue" && (
            <div>{t("game:levelup_rogue_proficiency")}</div>
          )}
          {charClass === "paladin" && (
            <>
              <div>{t("game:levelup_paladin_spell_slot")}</div>
              <label className="flex flex-col gap-1">
                <span>{t("game:levelup_fighting_style_label")}</span>
                <select
                  aria-label={t("game:levelup_fighting_style_label")}
                  className="rounded border border-border bg-background px-2 py-1"
                  value={style}
                  onChange={(e) => setStyle(e.target.value as FightingStyle | "")}
                >
                  <option value="">
                    {t("game:levelup_fighting_style_placeholder")}
                  </option>
                  {FIGHTING_STYLES.map((s) => (
                    <option key={s} value={s}>
                      {t(`game:levelup_fighting_style_${s}`)}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

          {error && (
            <div
              data-testid="level-up-error"
              className="text-red-400"
              role="alert"
            >
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            onClick={handleConfirm}
            disabled={!canConfirm}
          >
            {t("game:levelup_confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
