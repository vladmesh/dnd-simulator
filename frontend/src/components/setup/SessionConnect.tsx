import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface Props {
  onConnect: (sessionId: string) => void
}

export function SessionConnect({ onConnect }: Props) {
  const { t } = useTranslation(["setup", "common"])
  const [value, setValue] = useState("")

  return (
    <div className="space-y-3">
      <Label>Session ID</Label>
      <div className="flex gap-2">
        <Input
          placeholder={t("setup:session_id_placeholder")}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && value.trim() && onConnect(value.trim())}
        />
        <Button size="sm" disabled={!value.trim()} onClick={() => onConnect(value.trim())}>
          {t("common:join")}
        </Button>
      </div>
    </div>
  )
}
