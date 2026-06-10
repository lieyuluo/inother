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
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // keep status text fallback
    }
    throw new Error(detail)
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
        onError(`HTTP ${res.status}`)
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
