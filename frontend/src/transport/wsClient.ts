import type { ClientMessage, ServerMessage } from "@/types/ws"

type MessageHandler = (msg: ServerMessage) => void
type StatusHandler = (status: WsStatus) => void

export type WsStatus = "disconnected" | "connecting" | "connected" | "error"

const INITIAL_RETRY_MS = 1000
const MAX_RETRY_MS = 30000

export class WsClient {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private messageHandlers = new Set<MessageHandler>()
  private statusHandlers = new Set<StatusHandler>()
  private status: WsStatus = "disconnected"
  private retryMs = INITIAL_RETRY_MS
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private intentionalClose = false

  getStatus(): WsStatus {
    return this.status
  }

  connect(sessionId: string): void {
    this.intentionalClose = false
    this.sessionId = sessionId
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

    this.setStatus("connecting")

    const proto = location.protocol === "https:" ? "wss:" : "ws:"
    const url = `${proto}//${location.host}/api/ws/${this.sessionId}`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.setStatus("connected")
      this.retryMs = INITIAL_RETRY_MS
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as ServerMessage
        for (const handler of this.messageHandlers) {
          handler(msg)
        }
      } catch {
        // ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      this.ws = null
      if (!this.intentionalClose && this.sessionId) {
        this.setStatus("disconnected")
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
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
