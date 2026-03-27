import { useEffect } from "react"
import { X } from "lucide-react"
import { useTranslation } from "react-i18next"
import { EventLog } from "./EventLog"

interface LogOverlayProps {
  onClose: () => void
}

export function LogOverlay({ onClose }: LogOverlayProps) {
  const { t } = useTranslation(["game"])

  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose()
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [onClose])

  return (
    <div
      data-testid="log-overlay"
      className="absolute inset-0 z-50 flex flex-col bg-background/90 backdrop-blur-sm"
      onClick={(e) => {
        // Close on backdrop click (only if clicking the backdrop itself)
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      {/* Overlay header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-sm font-medium">{t("game:event_log")}</span>
        <button
          data-testid="log-overlay-close"
          className="text-muted-foreground transition-colors hover:text-foreground"
          onClick={onClose}
        >
          <X className="size-4" />
        </button>
      </div>

      {/* Full virtualized log */}
      <div className="flex-1 overflow-hidden">
        <EventLog />
      </div>
    </div>
  )
}
