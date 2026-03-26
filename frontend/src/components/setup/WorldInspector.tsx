import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import type { LayerInfo } from "@/types/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { LayerEditor } from "@/components/master/LayerEditor"

interface Props {
  worldId: string
}

export function WorldInspector({ worldId }: Props) {
  const { t, i18n } = useTranslation(["master"])
  const [layers, setLayers] = useState<LayerInfo[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [forkingLayer, setForkingLayer] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editingLayer, setEditingLayer] = useState<{ type: string; readOnly: boolean } | null>(null)

  useEffect(() => {
    setLoading(true)
    api.master
      .getWorldManifest(worldId, i18n.language)
      .then((data) => setLayers(data.layers))
      .catch(() => setError(t("master:layers_load_error")))
      .finally(() => setLoading(false))
  }, [worldId, i18n.language, t])

  const handleFork = (layerType: string) => {
    setForkingLayer(layerType)
    setError(null)
    api.master
      .forkLayer(worldId, layerType)
      .then(() =>
        api.master.getWorldManifest(worldId, i18n.language).then((data) => setLayers(data.layers)),
      )
      .catch(() => setError(t("master:fork_error")))
      .finally(() => setForkingLayer(null))
  }

  const handleEdit = (layerType: string, readOnly: boolean) => {
    if (editingLayer?.type === layerType) {
      setEditingLayer(null)
    } else {
      setEditingLayer({ type: layerType, readOnly })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-3">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <div className="py-2 text-xs text-destructive">{error}</div>
  }

  if (!layers) return null

  const layerLabel = (lt: string) => t(`master:layer_${lt}`, lt)

  return (
    <div className="space-y-1.5">
      {layers.map((layer) => (
        <div key={layer.layer_type}>
          <div className="flex items-center justify-between gap-2 rounded border border-border/50 px-2.5 py-1.5 text-xs">
            <span className="font-medium">{layerLabel(layer.layer_type)}</span>
            <div className="flex items-center gap-2">
              {layer.source === "library" ? (
                <>
                  <Badge variant="outline">{t("master:source_library")}: {layer.template}</Badge>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => handleEdit(layer.layer_type, true)}
                  >
                    {t("master:editor_view")}
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    disabled={forkingLayer !== null}
                    onClick={() => handleFork(layer.layer_type)}
                  >
                    {forkingLayer === layer.layer_type && (
                      <Loader2 className="mr-1 size-3 animate-spin" />
                    )}
                    {t("master:fork_btn")}
                  </Button>
                </>
              ) : (
                <>
                  <Badge variant="secondary">{t("master:source_custom")}</Badge>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => handleEdit(layer.layer_type, false)}
                  >
                    {t("master:editor_edit")}
                  </Button>
                </>
              )}
            </div>
          </div>
          {editingLayer?.type === layer.layer_type && (
            <LayerEditor
              worldId={worldId}
              layerType={layer.layer_type}
              readOnly={editingLayer.readOnly}
              onClose={() => setEditingLayer(null)}
            />
          )}
        </div>
      ))}
    </div>
  )
}
