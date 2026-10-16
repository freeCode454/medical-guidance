// WebSocket 封装：换取一次性票据 + 连接 + 事件分发
import { http } from './client'

export interface WsEvent {
  type: string
  seq: number
  ts: number
  data: Record<string, any>
}

export interface WsHandlers {
  onConnected?: () => void
  onNodeComplete?: (node: string, output: Record<string, any>) => void
  onTaskComplete?: (data: Record<string, any>) => void
  onEmergency?: (data: Record<string, any>) => void
  onError?: (err: Error) => void
}

async function getWsTicket(sessionId: string): Promise<string> {
  const data = await http.post<{ ws_ticket: string }>('/ws/ticket', {
    resource_type: 'SESSION',
    resource_id: sessionId,
  })
  return data.ws_ticket
}

export function connectWs(sessionId: string, handlers: WsHandlers): () => void {
  let ws: WebSocket | null = null
  let closed = false

  getWsTicket(sessionId)
    .then((ticket) => {
      if (closed) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${location.host}/api/v1/ws/sessions/${sessionId}?token=${ticket}`
      ws = new WebSocket(url)

      ws.onmessage = (ev) => {
        try {
          const event: WsEvent = JSON.parse(ev.data)
          switch (event.type) {
            case 'connected':
              handlers.onConnected?.()
              break
            case 'node_complete':
              handlers.onNodeComplete?.(event.data?.node, event.data?.output ?? {})
              break
            case 'task_complete':
              handlers.onTaskComplete?.(event.data)
              break
            case 'emergency':
              handlers.onEmergency?.(event.data)
              break
          }
        } catch {
          // 忽略无法解析的消息
        }
      }

      ws.onerror = () => handlers.onError?.(new Error('WebSocket 连接失败'))
    })
    .catch((err) => handlers.onError?.(err))

  // 返回关闭函数
  return () => {
    closed = true
    ws?.close()
  }
}
