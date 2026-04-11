import { useState, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Loader2 } from "lucide-react"

const RACES = ["human", "elf", "dwarf", "halfling", "gnome", "half_orc", "half_elf", "tiefling", "dragonborn"] as const
const CLASSES = ["fighter", "rogue", "paladin"] as const
const ALIGNMENTS = [
  "lawful_good", "neutral_good", "chaotic_good",
  "lawful_neutral", "true_neutral", "chaotic_neutral",
  "lawful_evil", "neutral_evil", "chaotic_evil",
] as const
const ABILITY_NAMES = ["str", "dex", "con", "int", "wis", "cha"] as const
type AbilityName = (typeof ABILITY_NAMES)[number]

const FIGHTING_STYLES = ["defense", "dueling", "great_weapon_fighting"] as const

// D&D 5e point buy cost table
const POINT_BUY_COSTS: Record<number, number> = {
  8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9,
}
// POINT_BUY_BUDGET is dynamically fetched

// Hit die per class
const HIT_DICE: Record<string, number> = { fighter: 10, rogue: 8, paladin: 10 }

// Starting equipment display
const STARTING_EQUIPMENT: Record<string, string[]> = {
  fighter: ["Chain Mail", "Longsword", "Shield"],
  fighter_gwf: ["Chain Mail", "Greatsword"],
  rogue: ["Leather Armor", "Rapier", "Shortbow", "Dagger"],
  paladin: ["Chain Mail", "Longsword", "Shield"],
}

// STARTING_GOLD is dynamically fetched

function abilityModifier(score: number): number {
  return Math.floor((score - 10) / 2)
}

function totalPointCost(scores: Record<AbilityName, number>): number {
  return ABILITY_NAMES.reduce((sum, ab) => sum + POINT_BUY_COSTS[scores[ab]], 0)
}

function previewHp(charClass: string, conScore: number): number {
  const hitDie = HIT_DICE[charClass] ?? 10
  return Math.max(hitDie + abilityModifier(conScore), 1)
}

function previewAc(charClass: string, dexScore: number, fightingStyle: string): number {
  if (charClass === "fighter") {
    if (fightingStyle === "great_weapon_fighting") {
      // Chain mail (16), no shield (two-handed weapon)
      return 16
    }
    // Chain mail (16) + shield (+2) + defense (+1 if selected)
    const base = 16 + 2
    return fightingStyle === "defense" ? base + 1 : base
  }
  if (charClass === "paladin") {
    // Chain mail (16) + shield (+2)
    return 18
  }
  // Rogue: leather (11) + DEX mod (no cap for light armor)
  return 11 + abilityModifier(dexScore)
}

function getEquipmentKey(charClass: string, fightingStyle: string): string {
  if (charClass === "fighter" && fightingStyle === "great_weapon_fighting") return "fighter_gwf"
  return charClass
}

interface Props {
  sessionId: string
  onCreated: (playerId: string) => void
}

export function CharacterForm({ sessionId, onCreated }: Props) {
  const { t } = useTranslation(["setup", "common"])
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [submitAttempted, setSubmitAttempted] = useState(false)

  const [startingGold, setStartingGold] = useState(100)
  const [pointBuyBudget, setPointBuyBudget] = useState(27)

  useEffect(() => {
    api.player.getSetupConfig().then((cfg) => {
      setStartingGold(cfg.starting_gold)
      setPointBuyBudget(cfg.point_buy_budget)
    }).catch((e) => console.error("Failed to fetch setup config:", e))
  }, [])

  const [name, setName] = useState("Adventurer")
  const [race, setRace] = useState<string>("human")
  const [charClass, setCharClass] = useState<string>("fighter")
  const [alignment, setAlignment] = useState<string>("true_neutral")
  const [fightingStyle, setFightingStyle] = useState<string>("")
  const [scores, setScores] = useState<Record<AbilityName, number>>({
    str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10,
  })

  const remaining = pointBuyBudget - totalPointCost(scores)

  const canIncrement = (ab: AbilityName): boolean => {
    if (scores[ab] >= 15) return false
    const nextCost = POINT_BUY_COSTS[scores[ab] + 1] - POINT_BUY_COSTS[scores[ab]]
    return nextCost <= remaining
  }

  const canDecrement = (ab: AbilityName): boolean => scores[ab] > 8

  const increment = (ab: AbilityName) => {
    if (!canIncrement(ab)) return
    setScores((prev) => ({ ...prev, [ab]: prev[ab] + 1 }))
  }

  const decrement = (ab: AbilityName) => {
    if (!canDecrement(ab)) return
    setScores((prev) => ({ ...prev, [ab]: prev[ab] - 1 }))
  }

  const handleClassChange = (newClass: string) => {
    setCharClass(newClass)
    setSubmitAttempted(false)
    if (newClass !== "fighter") {
      setFightingStyle("")
    }
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitAttempted(true)
    if (charClass === "fighter" && !fightingStyle) {
      return
    }

    setSubmitting(true)
    setServerError(null)
    try {
      const payload: Record<string, unknown> = {
        name,
        race,
        char_class: charClass,
        alignment,
        ability_scores: { ...scores },
      }
      if (charClass === "fighter" && fightingStyle) {
        payload.fighting_style = fightingStyle
      }
      const result = await api.player.createCharacter(sessionId, payload as unknown as Parameters<typeof api.player.createCharacter>[1])
      onCreated(result.player_id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("setup:create_character_error")
      setServerError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const hp = previewHp(charClass, scores.con)
  const ac = previewAc(charClass, scores.dex, fightingStyle)
  const equipment = STARTING_EQUIPMENT[getEquipmentKey(charClass, fightingStyle)] ?? []

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="text-xs text-muted-foreground">{t("setup:session_label", { id: sessionId })}</div>

      {/* Basic info */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("setup:field_name")}>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>

        <Field label={t("setup:field_race")}>
          <select
            value={race}
            onChange={(e) => setRace(e.target.value)}
            className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground"
          >
            {RACES.map((r) => <option key={r} value={r}>{t(`setup:race_${r}`)}</option>)}
          </select>
        </Field>

        <Field label={t("setup:field_class")}>
          <select
            data-testid="class-select"
            value={charClass}
            onChange={(e) => handleClassChange(e.target.value)}
            className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground"
          >
            {CLASSES.map((c) => <option key={c} value={c}>{t(`setup:class_${c}`)}</option>)}
          </select>
        </Field>

        <Field label={t("setup:field_alignment")}>
          <select
            value={alignment}
            onChange={(e) => setAlignment(e.target.value)}
            className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground"
          >
            {ALIGNMENTS.map((a) => <option key={a} value={a}>{t(`setup:alignment_${a}`)}</option>)}
          </select>
        </Field>
      </div>

      {/* Fighting style — fighter only */}
      {charClass === "fighter" && (
        <Field label={t("setup:field_fighting_style")}>
          <select
            data-testid="fighting-style-select"
            value={fightingStyle}
            onChange={(e) => {
              setFightingStyle(e.target.value)
              if (e.target.value) setSubmitAttempted(false)
            }}
            className={`h-8 w-full rounded-lg border bg-background px-2.5 text-sm text-foreground ${
              submitAttempted && !fightingStyle 
                ? "border-destructive ring-1 ring-destructive" 
                : "border-input"
            }`}
          >
            <option value="" disabled>{t("setup:fighting_style_none")}</option>
            {FIGHTING_STYLES.map((s) => (
              <option key={s} value={s}>{t(`setup:fighting_style_${s}`)}</option>
            ))}
          </select>
        </Field>
      )}

      {/* Point buy ability scores */}
      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t("setup:ability_scores")}</legend>
        <div className="mb-2 text-sm">
          {t("setup:remaining_points")}: <span data-testid="remaining-points">{remaining}</span> / {pointBuyBudget}
        </div>
        <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
          {ABILITY_NAMES.map((ab) => {
            const mod = abilityModifier(scores[ab])
            const modStr = mod >= 0 ? `+${mod}` : `${mod}`
            return (
              <div key={ab} className="space-y-1 text-center">
                <Label>{t(`common:ability_${ab}`)}</Label>
                <div className="flex items-center justify-center gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    data-testid={`${ab}-minus`}
                    disabled={!canDecrement(ab)}
                    onClick={() => decrement(ab)}
                    className="h-7 w-7 p-0"
                  >
                    -
                  </Button>
                  <span data-testid={`${ab}-score`} className="w-8 text-center font-mono text-lg">
                    {scores[ab]}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    data-testid={`${ab}-plus`}
                    disabled={!canIncrement(ab)}
                    onClick={() => increment(ab)}
                    className="h-7 w-7 p-0"
                  >
                    +
                  </Button>
                </div>
                <div data-testid={`${ab}-modifier`} className="text-xs text-muted-foreground">
                  {modStr}
                </div>
              </div>
            )
          })}
        </div>
      </fieldset>

      {/* Preview */}
      <div className="rounded-lg border p-4 space-y-2">
        <div className="text-sm font-medium">{t("setup:preview_title")}</div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>HP: <span data-testid="preview-hp">{hp}</span></div>
          <div>AC: <span data-testid="preview-ac">{ac}</span></div>
          <div>{t("setup:field_gold")}: <span data-testid="preview-gold">{startingGold}</span></div>
        </div>
        <div data-testid="preview-equipment" className="text-sm">
          {t("setup:starting_equipment")}: {equipment.join(", ")}
        </div>
      </div>

      {serverError && <div className="text-sm text-destructive">{serverError}</div>}

      <Button type="submit" disabled={submitting} className="w-full">
        {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
        {t("setup:create_character_btn")}
      </Button>
    </form>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
    </div>
  )
}
