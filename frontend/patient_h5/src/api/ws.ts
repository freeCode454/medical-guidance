// WebSocket 封装：换取一次性票据 + 连接 + 断线重连 + 事件分发
import { http } from './client'

export interface WsEvent {
  type: string
  seq: number
  ts: number
  data: Record<string, any>
}

export interface WsHandlers {
  /** 连接建立（含断线重连成功）时触发，上层借此补拉错过的消息 */
  onConnected?: () => void
  onNodeComplete?: (node: string, output: Record<string, any>) => void
  onTaskComplete?: (data: Record<string, any>) => void
  onEmergency?: (data: Record<string, any>) => void
  /** 服务端返回的业务错误帧（会话已关闭、消息落库失败等） */
  onServerError?: (code: number, message: string) => void
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
  let retry = 0

  async function connect() {
    try {
      const ticket = await getWsTicket(sessionId)
      if (closed) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${location.host}/api/v1/ws/sessions/${sessionId}?token=${ticket}`
      ws = new WebSocket(url)

      ws.onopen = () => {
        retry = 0
        handlers.onConnected?.()
      }

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
            case 'error':
              handlers.onServerError?.(
                Number(event.data?.code ?? 0),
                String(event.data?.message ?? '消息处理失败'),
              )
              break
          }
        } catch {
          // 忽略无法解析的消息
        }
      }

      ws.onclose = () => {
        if (closed) return
        // 断线自动重连：页面长时间挂着（问诊中去看别的页面）时，连接可能被
        // 服务端或中间层超时断开。不重连的话下一个问题就收不到了。
        retry += 1
        if (retry > 5) {
          handlers.onError?.(new Error('连接已断开，请刷新页面'))
          return
        }
        setTimeout(() => {
          if (!closed) void connect()
        }, Math.min(2000 * retry, 8000))
      }

      ws.onerror = () => handlers.onError?.(new Error('WebSocket 连接失败'))
    } catch (err) {
      handlers.onError?.(err as Error)
    }
  }

  void connect()

  // 返回关闭函数
  return () => {
    closed = true
    ws?.close()
  }
}
