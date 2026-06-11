import type {
  AdminConfig,
  AdminDocument,
  AdminMetrics,
  AdminOverview,
  AdminTool,
  AdminUser,
  AuditLogEntry,
  LoginResponse,
  MCPServerStatus,
  RegisterRequest,
  User,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'enterprise_ai_agent_token'

export class ApiError extends Error {
  status: number
  code?: string
  details?: unknown

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    throw await buildApiError(res)
  }

  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

function jsonRequest<T>(path: string, body: unknown, init: RequestInit = {}): Promise<T> {
  return request<T>(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
    body: JSON.stringify(body),
  })
}

export const api = {
  getToken,

  setToken,

  async health(): Promise<{ status: string; service: string; version: string }> {
    return request('/health')
  },

  async register(input: RegisterRequest): Promise<User> {
    return jsonRequest('/api/auth/register', input, { method: 'POST' })
  },

  async login(email: string, password: string): Promise<LoginResponse> {
    const res = await jsonRequest<LoginResponse>(
      '/api/auth/login',
      { email, password },
      { method: 'POST' },
    )
    setToken(res.access_token)
    return res
  },

  async me(): Promise<User> {
    return request('/api/auth/me')
  },

  logout(): void {
    setToken(null)
  },

  async listDocuments(): Promise<{ documents: unknown[]; total: number }> {
    return request('/api/documents')
  },

  async uploadDocument(file: File, visibility: string = 'private'): Promise<unknown> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('visibility', visibility)
    return request('/api/documents/upload', { method: 'POST', body: formData })
  },

  async deleteDocument(id: string): Promise<void> {
    await request(`/api/documents/${id}`, { method: 'DELETE' })
  },

  async listSessions(): Promise<{ sessions: unknown[]; total: number }> {
    return request('/api/chat/sessions')
  },

  async createSession(title?: string): Promise<unknown> {
    return jsonRequest('/api/chat/sessions', title ? { title } : {}, { method: 'POST' })
  },

  async getMessages(sessionId: string): Promise<{ messages: unknown[]; total: number }> {
    return request(`/api/chat/sessions/${sessionId}/messages`)
  },

  async sendMessage(
    sessionId: string,
    content: string,
    mode?: string,
  ): Promise<unknown> {
    const body: Record<string, unknown> = { content }
    if (mode && mode !== 'rag') {
      body.mode = mode
    }
    return jsonRequest(`/api/chat/sessions/${sessionId}/messages`, body, { method: 'POST' })
  },

  async sendMessageStream(
    sessionId: string,
    content: string,
    mode: string | undefined,
    onEvent: (event: string, data: unknown) => void,
    onError: (error: string) => void,
  ): Promise<void> {
    const body: Record<string, unknown> = { content }
    if (mode && mode !== 'rag') {
      body.mode = mode
    }

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      const token = getToken()
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        onError((await buildApiError(res)).message)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        onError('No response body')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue

          let eventType = ''
          let eventData = ''

          for (const line of part.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6)
            }
          }

          if (eventType && eventData) {
            try {
              const parsed = JSON.parse(eventData)
              onEvent(eventType, parsed)
            } catch {
              onEvent(eventType, eventData)
            }
          }
        }
      }
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Stream error')
    }
  },

  async listTools(): Promise<{ tools: unknown[]; total: number }> {
    return request('/api/tools')
  },

  async invokeTool(name: string, input: Record<string, unknown>): Promise<unknown> {
    return jsonRequest(`/api/tools/${name}/invoke`, { input }, { method: 'POST' })
  },

  // Admin API
  async getAdminOverview(): Promise<AdminOverview> {
    return request('/api/admin/overview')
  },

  async getAdminUsers(): Promise<{ users: AdminUser[]; total: number }> {
    return request('/api/admin/users')
  },

  async patchAdminUser(userId: string, data: { is_active?: boolean; role?: string }): Promise<AdminUser> {
    return jsonRequest(`/api/admin/users/${userId}`, data, { method: 'PATCH' })
  },

  async getAdminDocuments(): Promise<{ documents: AdminDocument[]; total: number }> {
    return request('/api/admin/documents')
  },

  async getAdminTools(): Promise<{ tools: AdminTool[]; total: number }> {
    return request('/api/admin/tools')
  },

  async getAdminMcpServers(): Promise<{ servers: MCPServerStatus[]; total: number }> {
    return request('/api/admin/mcp-servers')
  },

  async getAdminConfig(): Promise<AdminConfig> {
    return request('/api/admin/config')
  },

  async getAdminMetrics(): Promise<AdminMetrics> {
    return request('/api/admin/metrics')
  },

  async getAdminAuditLogs(action?: string): Promise<{ logs: AuditLogEntry[]; total: number }> {
    const params = action ? `?action=${encodeURIComponent(action)}` : ''
    return request(`/api/admin/audit-logs${params}`)
  },
}

async function buildApiError(res: Response): Promise<ApiError> {
  let body: unknown
  try {
    body = await res.json()
  } catch {
    body = null
  }

  const message = getErrorMessage(body, res.status)
  const code = getStringField(body, 'code')
  const details = getObjectField(body, 'details')
  return new ApiError(message, res.status, code, details)
}

function getErrorMessage(body: unknown, status: number): string {
  if (isRecord(body)) {
    const message = getStringField(body, 'message')
    if (message) return message

    const error = getStringField(body, 'error')
    if (error) return error

    const detail = body.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const readable = formatValidationDetails(detail)
      if (readable) return readable
    }
  }

  switch (status) {
    case 400:
      return '请求参数不正确，请检查后重试。'
    case 401:
      return '请先登录或重新登录后再试。'
    case 403:
      return '当前账号没有权限执行此操作。'
    case 404:
      return '请求的资源不存在或你无权访问。'
    case 409:
      return '数据已存在，请换一个值后重试。'
    case 422:
      return '请求参数没有通过校验，请检查输入内容。'
    case 500:
      return '服务器内部错误，请稍后重试。'
    case 502:
      return 'AI 服务返回异常，请检查模型、额度或稍后重试。'
    case 504:
      return 'AI 服务响应超时，请稍后重试。'
    default:
      return `请求失败：HTTP ${status}`
  }
}

function formatValidationDetails(detail: unknown[]): string {
  const messages = detail
    .map((item) => {
      if (!isRecord(item)) return ''
      const loc = Array.isArray(item.loc) ? item.loc.map(String) : []
      const field = loc.filter((part) => !['body', 'query', 'path'].includes(part)).join('.')
      const msg = typeof item.msg === 'string' ? item.msg : ''
      return field && msg ? `${field}: ${msg}` : msg
    })
    .filter(Boolean)
  return messages.length > 0 ? `请求参数不正确：${messages.join('; ')}` : ''
}

function getStringField(value: unknown, key: string): string | undefined {
  if (!isRecord(value)) return undefined
  const field = value[key]
  return typeof field === 'string' && field ? field : undefined
}

function getObjectField(value: unknown, key: string): unknown {
  if (!isRecord(value)) return undefined
  return value[key]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
