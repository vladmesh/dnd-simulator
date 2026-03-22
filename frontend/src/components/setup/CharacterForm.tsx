import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import { api } from "@/transport/apiClient"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Loader2 } from "lucide-react"

const RACES = ["human", "elf", "dwarf", "halfling", "gnome", "half-orc", "half-elf", "tiefling", "dragonborn"] as const
const CLASSES = ["fighter", "wizard", "rogue", "cleric", "ranger", "paladin", "barbarian", "bard", "druid", "monk", "sorcerer", "warlock"] as const
const ALIGNMENTS = [
  "lawful_good", "neutral_good", "chaotic_good",
  "lawful_neutral", "true_neutral", "chaotic_neutral",
  "lawful_evil", "neutral_evil", "chaotic_evil",
] as const
const ABILITY_NAMES = ["str", "dex", "con", "int", "wis", "cha"] as const

const characterSchema = z.object({
  name: z.string().min(1, "validation_name_required").max(50),
  race: z.string().min(1),
  char_class: z.string().min(1),
  level: z.number().int().min(1).max(20),
  alignment: z.string().min(1),
  hp: z.number().int().min(1).max(999),
  ac: z.number().int().min(0).max(30),
  gold: z.number().int().min(0),
  str: z.number().int().min(1).max(30),
  dex: z.number().int().min(1).max(30),
  con: z.number().int().min(1).max(30),
  int: z.number().int().min(1).max(30),
  wis: z.number().int().min(1).max(30),
  cha: z.number().int().min(1).max(30),
})

type CharacterFormData = z.infer<typeof characterSchema>

interface Props {
  sessionId: string
  onCreated: () => void
}

export function CharacterForm({ sessionId, onCreated }: Props) {
  const { t } = useTranslation(["setup", "common"])
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CharacterFormData>({
    resolver: zodResolver(characterSchema),
    defaultValues: {
      name: "Adventurer",
      race: "human",
      char_class: "fighter",
      level: 1,
      alignment: "true_neutral",
      hp: 10,
      ac: 10,
      gold: 0,
      str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10,
    },
  })

  const onSubmit = async (data: CharacterFormData) => {
    setSubmitting(true)
    setServerError(null)
    try {
      const { str, dex, con, int, wis, cha, ...rest } = data
      await api.player.createCharacter(sessionId, {
        ...rest,
        ability_scores: { str, dex, con, int, wis, cha },
      })
      onCreated()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("setup:create_character_error")
      setServerError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const translateError = (msg?: string) => {
    if (!msg) return undefined
    // Zod validation keys are stored as translation keys
    if (msg.startsWith("validation_")) return t(`setup:${msg}`)
    return msg
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div className="text-xs text-muted-foreground">{t("setup:session_label", { id: sessionId })}</div>

      {/* Basic info */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("setup:field_name")} error={translateError(errors.name?.message)}>
          <Input {...register("name")} />
        </Field>

        <Field label={t("setup:field_race")} error={errors.race?.message}>
          <select {...register("race")} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground">
            {RACES.map((r) => <option key={r} value={r}>{t(`setup:race_${r}`)}</option>)}
          </select>
        </Field>

        <Field label={t("setup:field_class")} error={errors.char_class?.message}>
          <select {...register("char_class")} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground">
            {CLASSES.map((c) => <option key={c} value={c}>{t(`setup:class_${c}`)}</option>)}
          </select>
        </Field>

        <Field label={t("setup:field_alignment")} error={errors.alignment?.message}>
          <select {...register("alignment")} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground">
            {ALIGNMENTS.map((a) => <option key={a} value={a}>{t(`setup:alignment_${a}`)}</option>)}
          </select>
        </Field>
      </div>

      {/* Combat stats */}
      <div className="grid grid-cols-4 gap-4">
        <Field label={t("setup:field_level")} error={errors.level?.message}>
          <Input type="number" {...register("level", { valueAsNumber: true })} />
        </Field>
        <Field label={t("setup:field_hp")} error={errors.hp?.message}>
          <Input type="number" {...register("hp", { valueAsNumber: true })} />
        </Field>
        <Field label={t("setup:field_ac")} error={errors.ac?.message}>
          <Input type="number" {...register("ac", { valueAsNumber: true })} />
        </Field>
        <Field label={t("setup:field_gold")} error={errors.gold?.message}>
          <Input type="number" {...register("gold", { valueAsNumber: true })} />
        </Field>
      </div>

      {/* Ability scores */}
      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t("setup:ability_scores")}</legend>
        <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
          {ABILITY_NAMES.map((ab) => (
            <Field key={ab} label={t(`common:ability_${ab}`)} error={errors[ab]?.message}>
              <Input type="number" {...register(ab, { valueAsNumber: true })} className="text-center" />
            </Field>
          ))}
        </div>
      </fieldset>

      {serverError && <div className="text-sm text-destructive">{serverError}</div>}

      <Button type="submit" disabled={submitting} className="w-full">
        {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
        {t("setup:create_character_btn")}
      </Button>
    </form>
  )
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
