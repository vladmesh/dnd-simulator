/**
 * Client-side mirror of the server's speech bound (`MAX_PARAM_STRING_LENGTH` in
 * `service/action_parsing.py`). The server measures Python `len`, i.e. Unicode code points,
 * so an astral emoji counts once and a combining mark counts on its own — unlike JS
 * `String.length` (UTF-16 units) or the HTML `maxLength` attribute.
 */
export const MAX_SPEECH_LENGTH = 2000

/** Number of Unicode code points in `text` (what Python `len` reports). */
export function codePointLength(text: string): number {
  return Array.from(text).length
}

export interface SpeechCheck {
  /** The exact text that would be sent: the trimmed draft. */
  payload: string
  /** Code-point length of `payload`. */
  length: number
  tooLong: boolean
  /** True when `payload` is non-empty and within the bound. */
  canSend: boolean
}

export function checkSpeech(draft: string): SpeechCheck {
  const payload = draft.trim()
  const length = codePointLength(payload)
  const tooLong = length > MAX_SPEECH_LENGTH
  return { payload, length, tooLong, canSend: length > 0 && !tooLong }
}
