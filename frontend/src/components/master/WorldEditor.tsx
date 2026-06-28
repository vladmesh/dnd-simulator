import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { LayerInfo } from "@/types/api"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { EntityListEditor } from "./EntityListEditor"
import { CatalogPicker } from "./CatalogPicker"

// ---------------------------------------------------------------------------
// Layer → entity types mapping
// ---------------------------------------------------------------------------

const LAYER_ENTITY_TYPES: Record<string, string[]> = {
  geography: ["region", "location"],
  politics: ["nation"],
  settlements: ["settlement"],
  entities: ["npc"],
  ecology: ["squad", "monster_template"],
}

interface Props {
  worldId: string
  readOnly: boolean
  onClose: () => void
}

export function WorldEditor({ worldId, readOnly, onClose }: Props) {
  const { t, i18n } = useTranslation(["master"])
  const [layers, setLayers] = useState<LayerInfo[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [step, setStep] = useState(0)
  const [showCatalogPicker, setShowCatalogPicker] = useState(false)

  useEffect(() => {
    api.master
      .getWorldManifest(worldId, i18n.language)
      .then((data) => setLayers(data.layers))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [worldId, i18n.language])

  const handleCatalogPick = async (monsterId: string) => {
    await api.master.createEntity(worldId, "monster_template", monsterId, { base: monsterId })
    setShowCatalogPicker(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!layers) return null

  const currentLayer = layers[step]
  const entityTypes = LAYER_ENTITY_TYPES[currentLayer.layer_type]
  const layerLabel = (lt: string) => t(`master:layer_${lt}`, lt)

  return (
    <div className="space-y-4 pt-4">
      {/* Stepper header */}
      <div className="flex items-center gap-1">
        {layers.map((layer, i) => (
          <button
            key={layer.layer_type}
            className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
              i === step
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
            onClick={() => { setStep(i); setShowCatalogPicker(false) }}
          >
            {layerLabel(layer.layer_type)}
          </button>
        ))}
      </div>

      {/* Layer heading */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{layerLabel(currentLayer.layer_type)}</h3>
      </div>

      {/* Entity editors for current step */}
      {entityTypes && (
        <div className="space-y-3">
          {entityTypes.map((entityType) => (
            <div key={entityType}>
              <h4 className="mb-1 text-xs font-medium capitalize">{entityType.replace("_", " ")}s</h4>
              <EntityListEditor
                worldId={worldId}
                entityType={entityType}
                readOnly={readOnly}
              />
            </div>
          ))}
        </div>
      )}

      {/* Catalog picker for ecology */}
      {currentLayer.layer_type === "ecology" && !readOnly && (
        <div>
          {showCatalogPicker ? (
            <div className="rounded border border-border p-2">
              <div className="mb-1 flex items-center justify-between">
                <h4 className="text-xs font-medium">Pick from monster catalog</h4>
                <Button size="xs" variant="ghost" onClick={() => setShowCatalogPicker(false)}>
                  Cancel
                </Button>
              </div>
              <CatalogPicker catalogType="monster_catalog" onPick={handleCatalogPick} />
            </div>
          ) : (
            <Button size="xs" variant="outline" onClick={() => setShowCatalogPicker(true)}>
              Pick from catalog
            </Button>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={step === 0}
            onClick={() => { setStep(step - 1); setShowCatalogPicker(false) }}
          >
            {t("common:back")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={step === layers.length - 1}
            onClick={() => { setStep(step + 1); setShowCatalogPicker(false) }}
          >
            {t("master:next")}
          </Button>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose}>
          {t("master:close_editor")}
        </Button>
      </div>
    </div>
  )
}
