import { useTranslation } from "react-i18next"
import { MAX_SPEECH_LENGTH, type SpeechCheck } from "./speechLimit"

interface SpeechLengthErrorProps {
  id: string
  speech: SpeechCheck
}

/** Accessible feedback for an overlong speech draft; renders nothing while the draft is sendable. */
export function SpeechLengthError({ id, speech }: SpeechLengthErrorProps) {
  const { t } = useTranslation("game")
  if (!speech.tooLong) return null
  return (
    <p id={id} role="alert" className="text-[10px] text-red-400">
      {t("game:speech_too_long", { length: speech.length, max: MAX_SPEECH_LENGTH })}
    </p>
  )
}
