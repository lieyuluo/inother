const API_BASE = import.meta.env.VITE_API_URL || ''

export const api = {
  async health(): Promise<{ status: string; service: string; version: string }> {
    const res = await fetch(`${API_BASE}/health`)
    return res.json()
  },

  async listDocuments(): Promise<{ documents: unknown[]; total: number }> {
    const res = await fetch(`${API_BASE}/api/documents`)
    return res.json()
  },

  async uploadDocument(file: File): Promise<unknown> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_BASE}/api/documents/upload`, { method: 'POST', body: formData })
    return res.json()
  },

  async deleteDocument(id: string): Promise<void> {
    await fetch(`${API_BASE}/api/documents/${id}`, { method: 'DELETE' })
  },

  async listSessions(): Promise<{ sessions: unknown[]; total: number }> {
    const res = await fetch(`${API_BASE}/api/chat/sessions`)
    return res.json()
  },

  async createSession(title?: string): Promise<unknown> {
    const res = await fetch(`${API_BASE}/api/chat/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(title ? { content: title } : {}),
    })
    return res.json()
  },

  async getMessages(sessionId: string): Promise<{ messages: unknown[]; total: number }> {
    const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`)
    return res.json()
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
    const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return res.json()
  },

  /**
   * Send a message with SSE streaming.
   * Uses fetch + ReadableStream to parse SSE events from POST request.
   */
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
      const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

        // Parse SSE events from buffer
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
    const res = await fetch(`${API_BASE}/api/tools`)
    return res.json()
  },

  async invokeTool(name: string, input: Record<string, unknown>): Promise<unknown> {
    const res = await fetch(`${API_BASE}/api/tools/${name}/invoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input }),
    })
    return res.json()
  },
}
