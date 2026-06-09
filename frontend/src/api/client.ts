import type {
  Document,
  DocumentListResponse,
  HealthResponse,
  MessageListResponse,
  SendMessageResponse,
  Session,
  SessionListResponse,
  ToolInvokeResponse,
  ToolListResponse,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`API Error ${res.status}: ${text}`)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export const api = {
  // Health
  getHealth: () => request<HealthResponse>('/health'),

  // Documents
  uploadDocument: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<Document>('/api/documents/upload', {
      method: 'POST',
      headers: {},
      body: formData,
    })
  },
  getDocuments: () => request<DocumentListResponse>('/api/documents'),
  deleteDocument: (id: string) =>
    request<void>(`/api/documents/${id}`, { method: 'DELETE' }),

  // Chat Sessions
  createSession: (title?: string) =>
    request<Session>('/api/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: title || 'New Chat' }),
    }),
  getSessions: () => request<SessionListResponse>('/api/chat/sessions'),

  // Messages
  getMessages: (sessionId: string) =>
    request<MessageListResponse>(`/api/chat/sessions/${sessionId}/messages`),
  sendMessage: (sessionId: string, content: string, mode?: string) =>
    request<SendMessageResponse>(`/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, mode }),
    }),

  // Tools
  getTools: () => request<ToolListResponse>('/api/tools'),
  invokeTool: (toolName: string, input: Record<string, unknown>) =>
    request<ToolInvokeResponse>(`/api/tools/${toolName}/invoke`, {
      method: 'POST',
      body: JSON.stringify({ input }),
    }),
}
