import { useCallback, useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { TemplateListItem } from "@/types/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Loader2 } from "lucide-react"

const LAYER_STEPS = ["geography", "politics", "settlements", "ecology", "entities"] as const
type LayerStep = (typeof LAYER_STEPS)[number]
type WizardStep = LayerStep | "details"

const STEP_ORDER: WizardStep[] = [...LAYER_STEPS, "details"]

interface Props {
  onWorldAssembled: (sessionId: string) => void
  onBack: () => void
}

export function WorldBuilder({ onWorldAssembled, onBack }: Props) {
  const { t, i18n } = useTranslation(["setup", "common"])
  const [step, setStep] = useState<WizardStep>("geography")
  const [selections, setSelections] = useState<Partial<Record<LayerStep, string>>>({})

  const stepIndex = STEP_ORDER.indexOf(step)

  const goBack = useCallback(() => {
    if (stepIndex === 0) {
      onBack()
    } else {
      setStep(STEP_ORDER[stepIndex - 1])
    }
  }, [stepIndex, onBack])

  const selectTemplate = useCallback(
    (slug: string) => {
      const currentLayer = step as LayerStep
      setSelections((prev) => ({ ...prev, [currentLayer]: slug }))
      setStep(STEP_ORDER[stepIndex + 1])
    },
    [step, stepIndex],
  )

  const stepLabel = t(`setup:wizard_step_${step}`)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={goBack}>
          <ArrowLeft className="mr-1 size-4" />
          {t("setup:wizard_back")}
        </Button>
        <div className="text-sm text-muted-foreground">
          {t("setup:wizard_step_label", { current: stepIndex + 1, total: STEP_ORDER.length })}
        </div>
      </div>

      <h2 className="text-lg font-medium">{stepLabel}</h2>

      {step !== "details" ? (
        <LayerPicker
          layerType={step}
          geography={selections.geography}
          onSelect={selectTemplate}
        />
      ) : (
        <DetailsForm
          selections={selections as Record<LayerStep, string>}
          lang={i18n.language}
          onCreated={onWorldAssembled}
        />
      )}
    </div>
  )
}

// --- Layer template picker ---

function LayerPicker({
  layerType,
  geography,
  onSelect,
}: {
  layerType: LayerStep
  geography: string | undefined
  onSelect: (slug: string) => void
}) {
  const { t } = useTranslation(["setup"])
  const [templates, setTemplates] = useState<TemplateListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    const geoFilter = layerType !== "geography" ? geography : undefined
    api.master
      .getLibraryTemplates(layerType, geoFilter)
      .then(setTemplates)
      .catch(() => setError(t("setup:load_worlds_error")))
      .finally(() => setLoading(false))
  }, [layerType, geography, t])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <div className="py-8 text-center text-sm text-destructive">{error}</div>
  }

  if (templates.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        {t("setup:wizard_no_templates")}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{t("setup:wizard_select_template")}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {templates.map((tmpl) => (
          <Card
            key={tmpl.slug}
            className="cursor-pointer transition-colors hover:bg-accent/50"
            onClick={() => onSelect(tmpl.slug)}
          >
            <CardHeader>
              <CardTitle className="text-base">{tmpl.name}</CardTitle>
              <CardDescription>{tmpl.description}</CardDescription>
            </CardHeader>
            {tmpl.tags.length > 0 && (
              <CardContent>
                <div className="flex flex-wrap gap-1">
                  {tmpl.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}

// --- Final details form ---

function DetailsForm({
  selections,
  lang,
  onCreated,
}: {
  selections: Record<LayerStep, string>
  lang: string
  onCreated: (sessionId: string) => void
}) {
  const { t } = useTranslation(["setup"])
  const [worldId, setWorldId] = useState("")
  const [worldName, setWorldName] = useState("")
  const [description, setDescription] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isValid = /^[a-z0-9_]+$/.test(worldId) && worldName.trim().length > 0

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await api.master.assembleWorld({
        id: worldId,
        name: worldName.trim(),
        description: description.trim(),
        layer_selections: { ...selections },
      })
      const session = await api.master.createSession({ world_name: worldId, lang })
      onCreated(session.session_id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("setup:wizard_create_error")
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="space-y-1">
          <Label>{t("setup:wizard_field_id")}</Label>
          <Input
            value={worldId}
            onChange={(e) => setWorldId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
            placeholder="my_custom_world"
          />
          <p className="text-xs text-muted-foreground">{t("setup:wizard_field_id_hint")}</p>
        </div>

        <div className="space-y-1">
          <Label>{t("setup:wizard_field_name")}</Label>
          <Input
            value={worldName}
            onChange={(e) => setWorldName(e.target.value)}
            placeholder="My Custom World"
          />
        </div>

        <div className="space-y-1">
          <Label>{t("setup:wizard_field_description")}</Label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder=""
          />
        </div>
      </div>

      {error && <div className="text-sm text-destructive">{error}</div>}

      <Button onClick={handleSubmit} disabled={!isValid || submitting} className="w-full">
        {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
        {submitting ? t("setup:wizard_creating") : t("setup:wizard_create")}
      </Button>
    </div>
  )
}
