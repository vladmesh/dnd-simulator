import { useState } from "react"
import { useTranslation } from "react-i18next"
import { api } from "@/transport/apiClient"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, Clock } from "lucide-react"

interface Props {
  sessionId: string
  onAdvanced: () => void
}

export function TimeControl({ sessionId, onAdvanced }: Props) {
  const { t } = useTranslation(["master"])
  const [hours, setHours] = useState(1)
  const [advancing, setAdvancing] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const advance = () => {
    setAdvancing(true)
    setResult(null)
    api.master
      .advanceTime(sessionId, { hours })
      .then((res) => {
        setResult(res.message)
        onAdvanced()
      })
      .finally(() => setAdvancing(false))
  }

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="size-4" />
          {t("master:advance_time")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-3">
          <div>
            <Label>{t("master:hours")}</Label>
            <Input
              type="number"
              min={1}
              max={8760}
              className="w-24"
              value={hours}
              onChange={(e) => setHours(parseInt(e.target.value) || 1)}
            />
          </div>
          <Button onClick={advance} disabled={advancing}>
            {advancing && <Loader2 className="mr-1 size-3 animate-spin" />}
            {t("master:advance")}
          </Button>
        </div>

        {result && (
          <pre className="mt-4 max-h-48 overflow-auto whitespace-pre-wrap rounded border border-border bg-muted/30 p-3 text-xs">
            {result}
          </pre>
        )}
      </CardContent>
    </Card>
  )
}
