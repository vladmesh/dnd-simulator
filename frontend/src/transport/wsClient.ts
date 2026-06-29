import { useGameStore } from "@/store/gameStore"
import type { ClientMessage, ServerMessage } from "@/types/ws"

type MessageHandler = (msg: ServerMessage) => void
type StatusHandler = (status: WsStatus) => void

export type WsStatus = "disconnected" | "connecting" | "connected" | "error"

const INITIAL_RETRY_MS = 1000
const MAX_RETRY_MS = 30000

export class WsClient {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private playerId: string | null = null
  private messageHandlers = new Set<MessageHandler>()
  private statusHandlers = new Set<StatusHandler>()
  private status: WsStatus = "disconnected"
  private retryMs = INITIAL_RETRY_MS
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private intentionalClose = false

  getStatus(): WsStatus {
    return this.status
  }

  connect(sessionId: string, playerId?: string): void {
    this.intentionalClose = false
    this.sessionId = sessionId
    this.playerId = playerId ?? null
    this.retryMs = INITIAL_RETRY_MS
    this.doConnect()
  }

  disconnect(): void {
    this.intentionalClose = true
    this.sessionId = null
    if (this.retryTimer) {
      clearTimeout(this.retryTimer)
      this.retryTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.setStatus("disconnected")
  }

  send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler)
    return () => this.messageHandlers.delete(handler)
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler)
    return () => this.statusHandlers.delete(handler)
  }

  private doConnect(): void {
    if (!this.sessionId) return

    // Close any previous WS to avoid stale onclose clobbering new connection
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onclose = null
      this.ws.onerror = null
      this.ws.close()
      this.ws = null
    }

    this.setStatus("connecting")

    const proto = location.protocol === "https:" ? "wss:" : "ws:"
    let url = `${proto}//${location.host}/api/ws/${this.sessionId}`
    const params = new URLSearchParams()
    if (this.playerId) params.set("player_id", this.playerId)
    const { userId, role } = useGameStore.getState()
    if (userId) params.set("user_id", userId)
    if (role) params.set("role", role)
    const qs = params.toString()
    if (qs) url += `?${qs}`

    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      if (this.ws !== ws) return // stale
      this.setStatus("connected")
      this.retryMs = INITIAL_RETRY_MS
    }

    ws.onmessage = (event) => {
      if (this.ws !== ws) return // stale
      try {
        const msg = JSON.parse(event.data as string) as ServerMessage
        for (const handler of this.messageHandlers) {
          handler(msg)
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = (ev) => {
      if (this.ws !== ws) return // stale — a newer WS replaced us
      this.ws = null
      // 4004 = session not found or no player — don't reconnect
      if (ev.code === 4004) {
        this.setStatus("error")
        return
      }
      if (!this.intentionalClose && this.sessionId) {
        this.setStatus("disconnected")
        this.scheduleReconnect()
      }
    }

    ws.onerror = () => {
      if (this.ws !== ws) return // stale
      this.setStatus("error")
    }
  }

  private scheduleReconnect(): void {
    if (this.retryTimer) return
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      this.retryMs = Math.min(this.retryMs * 2, MAX_RETRY_MS)
      this.doConnect()
    }, this.retryMs)
  }

  private setStatus(status: WsStatus): void {
    if (this.status === status) return
    this.status = status
    for (const handler of this.statusHandlers) {
      handler(status)
    }
  }
}

export const wsClient = new WsClient()
