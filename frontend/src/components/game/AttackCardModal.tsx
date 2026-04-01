import { useTranslation } from "react-i18next"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { DieVisual } from "./DiceVisual"
import type { AttackRollData, DamageComponentData, DieRollData } from "@/types/game"
import { Swords } from "lucide-react"
import { cn } from "@/lib/utils"
import { hasAttackBreakdown } from "@/lib/logProcessing"

// ---------------------------------------------------------------------------
// Public data shape — extracted from event data by the consumer
// ---------------------------------------------------------------------------

export interface AttackCardData {
  attackerName: string
  targetName: string
  weapon: string
  hit: boolean
  critical: boolean
  ac: number
  attackRoll: AttackRollData
  totalDamage?: number       // actual damage dealt (after HP clamp)
  rolledDamage?: number      // total rolled damage (before HP clamp)
  damageComponents?: DamageComponentData[]
}

// ---------------------------------------------------------------------------
// AttackCardModal
// ---------------------------------------------------------------------------

interface AttackCardModalProps {
  data: AttackCardData
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AttackCardModal({ data, open, onOpenChange }: AttackCardModalProps) {
  const { t } = useTranslation(["game"])
  const verdict = data.critical ? t("game:verdict_crit") : data.hit ? t("game:verdict_hit") : t("game:verdict_miss")
  const verdictColor = data.critical
    ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
    : data.hit
      ? "bg-green-500/20 text-green-300 border-green-500/40"
      : "bg-red-500/20 text-red-300 border-red-500/40"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md font-mono">
        {/* Header */}
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Swords className="size-5 text-red-400" />
            <span>{t("game:attack_card_title", { weapon: data.weapon })}</span>
          </DialogTitle>
          <DialogDescription className="flex items-center justify-between">
            <span>
              {data.attackerName} → {data.targetName}
            </span>
            <span
              data-testid="verdict-badge"
              className={cn(
                "rounded border px-2 py-0.5 text-sm font-bold",
                verdictColor,
              )}
            >
              {verdict}
            </span>
          </DialogDescription>
        </DialogHeader>

        {/* Attack Roll */}
        <AttackRollSection
          roll={data.attackRoll}
          ac={data.ac}
          critical={data.critical}
          t={t}
        />

        {/* Damage (only on hit) */}
        {data.hit && data.damageComponents && data.damageComponents.length > 0 && (
          <DamageSection
            components={data.damageComponents}
            total={data.totalDamage}
            rolledTotal={data.rolledDamage}
            t={t}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Attack Roll Section
// ---------------------------------------------------------------------------

function AttackRollSection({
  roll,
  ac,
  critical,
  t,
}: {
  roll: AttackRollData
  ac: number
  critical: boolean
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  const hasAdvantage = roll.advantage || roll.disadvantage

  return (
    <div data-testid="attack-roll-section" className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {t("game:attack_roll")}
      </div>

      {/* d20 dice */}
      <div className="flex items-center gap-3">
        {hasAdvantage && roll.d20_alt ? (
          <AdvantageD20s
            kept={roll.d20}
            dropped={roll.d20_alt}
            advantage={roll.advantage}
            critical={critical}
            t={t}
          />
        ) : (
          <DieVisual sides={20} result={roll.natural} critical={critical} />
        )}
      </div>

      {/* Modifiers */}
      {roll.components.length > 0 && (
        <div className="space-y-0.5 pl-1">
          {roll.components.map((comp, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="w-8 text-right font-bold">
                {comp.value >= 0 ? "+" : ""}
                {comp.value}
              </span>
              <span className="text-muted-foreground">
                {t(`game:source_${comp.source}`, { defaultValue: comp.source })}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Total vs AC */}
      <div className="flex items-center gap-2 border-t border-border/30 pt-1 text-sm">
        <span className="font-bold">= {roll.total}</span>
        <span className="text-muted-foreground">{t("game:vs_ac", { ac })}</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Advantage / Disadvantage d20 display
// ---------------------------------------------------------------------------

function AdvantageD20s({
  kept,
  dropped,
  advantage,
  critical,
  t,
}: {
  kept: DieRollData
  dropped: DieRollData
  advantage: boolean
  critical: boolean
  t: (key: string) => string
}) {
  const label = advantage ? t("game:advantage") : t("game:disadvantage")
  return (
    <div className="flex items-center gap-2">
      <DieVisual sides={20} result={kept.result} critical={critical} />
      <DieVisual sides={20} result={dropped.result} dropped />
      <span className="text-xs text-muted-foreground">({label})</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Damage Section
// ---------------------------------------------------------------------------

function DamageSection({
  components,
  total,
  rolledTotal,
  t,
}: {
  components: DamageComponentData[]
  total?: number
  rolledTotal?: number
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  const hasOverkill = rolledTotal != null && total != null && rolledTotal > total
  return (
    <div data-testid="damage-section" className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {t("game:damage")}
      </div>

      {components.map((comp, i) => (
        <DamageComponentRow key={i} component={comp} t={t} />
      ))}

      {(rolledTotal ?? total) != null && (
        <div
          data-testid="total-damage"
          className="flex items-center gap-2 border-t border-border/30 pt-1 text-sm"
        >
          <span className="text-lg font-bold">= {rolledTotal ?? total}</span>
          <span className="text-muted-foreground">{t("game:damage_total")}</span>
          {hasOverkill && (
            <span className="text-muted-foreground text-xs">
              {t("game:damage_overkill", { dealt: total })}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Single damage component
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Extract AttackCardData from raw event data
// ---------------------------------------------------------------------------

export function extractAttackCardData(
  data: Record<string, unknown>,
): AttackCardData | null {
  if (!hasAttackBreakdown(data)) return null

  const attackRoll = data.attack_roll as AttackRollData
  const damageComponents = Array.isArray(data.damage_components)
    ? (data.damage_components as DamageComponentData[])
    : undefined

  return {
    attackerName: (data.attacker_name as string) ?? (data.attacker_id as string) ?? "?",
    targetName: (data.target_name as string) ?? (data.target_id as string) ?? "?",
    weapon: (data.weapon as string) ?? "Attack",
    hit: data.hit === true,
    critical: data.critical === true,
    ac: typeof data.ac === "number" ? data.ac : 0,
    attackRoll,
    totalDamage: typeof data.damage === "number" ? data.damage : undefined,
    rolledDamage: typeof data.total_damage === "number" ? data.total_damage : undefined,
    damageComponents,
  }
}

// ---------------------------------------------------------------------------
// Single damage component
// ---------------------------------------------------------------------------

function DamageComponentRow({
  component,
  t,
}: {
  component: DamageComponentData
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  const hasDice = component.dice_detail && component.dice_detail.length > 0
  const isFlat = !component.dice
  const isCritComponent = component.source.endsWith("_crit")
  const isWeaponBase = component.source === "weapon"
  const translatedType = t(`game:dmg_${component.type}`, { defaultValue: component.type })
  const translatedSource = t(`game:source_${component.source}`, { defaultValue: component.source })

  // GWF reroll reason: only on base weapon dice that have rerolls
  const gwfLabel = isWeaponBase ? t("game:gwf_short") : undefined

  return (
    <div className={cn(
      "space-y-1 rounded border p-2",
      isCritComponent
        ? "border-sky-400/40 bg-sky-950/20"
        : "border-border/20 bg-muted/30",
    )}>
      <div className="flex items-center justify-between text-xs">
        <span className={cn(
          "text-muted-foreground",
          isCritComponent && "text-sky-300 font-semibold",
        )}>
          {translatedSource}
        </span>
        {component.dice && (
          <span className="text-muted-foreground">
            {component.dice} {translatedType}
          </span>
        )}
      </div>

      {hasDice && (
        <div className="flex flex-wrap items-center gap-1">
          {component.dice_detail!.map((die, j) => (
            <DieVisual
              key={j}
              sides={die.sides}
              result={die.result}
              original={die.original}
              critical={isCritComponent}
              damageType={component.type}
              rerollReason={die.original != null ? gwfLabel : undefined}
            />
          ))}
        </div>
      )}

      {isFlat && (
        <div className="text-sm font-bold">
          +{component.amount} {translatedType}
        </div>
      )}
    </div>
  )
}
