import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { WsClient } from "@/transport/wsClient"
import type { ServerMessage } from "@/types/ws"

interface FeedItem {
  id: number
  description: string
  eventType: string
}

// Read-only live event feed for a master observing a session. Opens a dedicated
// spectator WebSocket (never the player singleton) and renders incoming
// `PerceivedEvent.description` lines, newest last.
export function SessionLiveFeed({ sessionId }: { sessionId: string }) {
  const { t } = useTranslation(["master"])
  const [items, setItems] = useState<FeedItem[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const seqRef = useRef(0)

  useEffect(() => {
    const client = new WsClient()
    const unsub = client.onMessage((msg: ServerMessage) => {
      if (msg.type !== "turn" && msg.type !== "action_result" && msg.type !== "round_result") return
      const events = msg.events ?? []
      if (events.length === 0) return
      setItems((prev) => [
        ...prev,
        ...events.map((e) => ({
          id: seqRef.current++,
          description: e.description,
          eventType: e.event_type,
        })),
      ])
    })
    client.connect(sessionId, { spectate: true })
    return () => {
      unsub()
      client.disconnect()
    }
  }, [sessionId])

  // Auto-scroll to newest line.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [items.length])

  return (
    <div
      ref={scrollRef}
      data-testid="live-feed"
      className="max-h-[28rem] overflow-y-auto rounded border border-border bg-muted/20 p-3 font-mono text-xs"
    >
      {items.length === 0 ? (
        <div className="text-muted-foreground">{t("master:live_empty")}</div>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.id} className="flex items-start gap-2">
              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                {item.eventType}
              </span>
              <span className="text-foreground">{item.description}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
