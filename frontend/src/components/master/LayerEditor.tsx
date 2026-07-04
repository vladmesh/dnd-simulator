import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { api, ApiError } from "@/transport/apiClient"
import { Button } from "@/components/ui/button"
import { Loader2, X } from "lucide-react"

interface Props {
  worldId: string
  layerType: string
  readOnly: boolean
  onClose: () => void
}

export function LayerEditor({ worldId, layerType, readOnly, onClose }: Props) {
  const { t } = useTranslation(["master"])
  const [files, setFiles] = useState<Record<string, string>>({})
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [content, setContent] = useState("")
  const [originalContent, setOriginalContent] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.master
      .getLayerFiles(worldId, layerType)
      .then((data) => {
        setError(null)
        setFiles(data.files)
        const filenames = Object.keys(data.files)
        if (filenames.length > 0) {
          const first = filenames[0]
          setSelectedFile(first)
          setContent(data.files[first])
          setOriginalContent(data.files[first])
        }
      })
      .catch(() => setError(t("master:editor_load_error")))
      .finally(() => setLoading(false))
  }, [worldId, layerType, t])

  const handleSelectFile = (filename: string) => {
    setSelectedFile(filename)
    setContent(files[filename])
    setOriginalContent(files[filename])
    setError(null)
  }

  const handleSave = () => {
    if (!selectedFile) return
    setSaving(true)
    setError(null)
    api.master
      .updateLayerFile(worldId, layerType, selectedFile, { content })
      .then(() => {
        setOriginalContent(content)
        setFiles((prev) => ({ ...prev, [selectedFile]: content }))
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.detailMessage() : String(err))
      })
      .finally(() => setSaving(false))
  }

  const dirty = content !== originalContent
  const filenames = Object.keys(files)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="mt-1.5 rounded border border-border bg-muted/30 p-2">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1">
          {filenames.map((f) => (
            <Button
              key={f}
              size="xs"
              variant={f === selectedFile ? "default" : "outline"}
              onClick={() => handleSelectFile(f)}
            >
              {f}
            </Button>
          ))}
        </div>
        <Button size="xs" variant="ghost" onClick={onClose}>
          <X className="size-3" />
        </Button>
      </div>

      {selectedFile && (
        <>
          <textarea
            className="h-64 w-full rounded border border-border bg-background p-2 font-mono text-xs"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            readOnly={readOnly}
            spellCheck={false}
          />

          {error && <div className="mt-1 text-xs text-destructive">{error}</div>}

          {!readOnly && (
            <div className="mt-1.5 flex justify-end">
              <Button size="xs" disabled={!dirty || saving} onClick={handleSave}>
                {saving && <Loader2 className="mr-1 size-3 animate-spin" />}
                {t("master:editor_save")}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
