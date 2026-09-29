import { useState, useRef, useId } from "react"
import { Button } from "@/components/ui/button"
import { getActionLabel, getCostTypeClass } from "./utils"
import { checkSpeech } from "../speechLimit"
import { SpeechLengthError } from "../SpeechLengthError"

interface SayActionProps {
  description: string
  disabled: boolean
  sendAction: (name: string, params?: Record<string, unknown>) => void
  t: (key: string, opts?: Record<string, unknown>) => string
}

export function SayAction({ description, disabled, sendAction, t }: SayActionProps) {
  const [sayOpen, setSayOpen] = useState(false)
  const [sayText, setSayText] = useState("")
  const sayInputRef = useRef<HTMLInputElement>(null)
  const errorId = useId()
  const speech = checkSpeech(sayText)

  const submit = () => {
    if (speech.canSend) {
      sendAction("say", { text: speech.payload })
      setSayText("")
      setSayOpen(false)
    }
  }

  if (sayOpen) {
    return (
      <div className="relative flex items-center gap-1">
        <input
          ref={sayInputRef}
          type="text"
          className="h-8 rounded border border-border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder={t("game:say_placeholder")}
          aria-invalid={speech.tooLong || undefined}
          aria-describedby={speech.tooLong ? errorId : undefined}
          value={sayText}
          onChange={(e) => setSayText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit()
            if (e.key === "Escape") {
              setSayText("")
              setSayOpen(false)
            }
          }}
          disabled={disabled}
          autoFocus
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={disabled || !speech.canSend}
          onClick={submit}
        >
          ↵
        </Button>
        <SpeechLengthError id={errorId} speech={speech} />
      </div>
    )
  }

  return (
    <div className="relative flex items-center gap-1">
      <Button
        size="sm"
        variant="secondary"
        disabled={disabled}
        title={description}
        className={getCostTypeClass("free")}
        data-cost-type="free"
        onClick={() => setSayOpen(true)}
      >
        {getActionLabel(t, "say")}
      </Button>
    </div>
  )
}
