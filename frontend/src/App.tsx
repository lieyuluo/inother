import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import { AuthPanel } from './components/AuthPanel'
import { AdminDashboard } from './components/AdminDashboard'
import { ChatSessionList } from './components/ChatSessionList'
import { ChatWindow } from './components/ChatWindow'
import { CitationList } from './components/CitationList'
import { DocumentList } from './components/DocumentList'
import { DocumentUpload } from './components/DocumentUpload'
import { HealthStatus } from './components/HealthStatus'
import { ToolPanel } from './components/ToolPanel'
import type { Document, Message, SendMessageResponse, Session, User } from './types'
import type { DocumentListResponse, MessageListResponse, SessionListResponse } from './types'

export default function App() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<SendMessageResponse | null>(null)
  const [messageList, setMessageList] = useState<Message[]>([])
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [currentUser, setCurrentUser] = useState<User | null>(null)

  const loadDocuments = useCallback(async () => {
    try {
      const res: DocumentListResponse = await api.listDocuments() as DocumentListResponse
      setDocuments(res.documents)
    } catch {
      // ignore
    }
  }, [])

  const loadSessions = useCallback(async () => {
    try {
      const res: SessionListResponse = await api.listSessions() as SessionListResponse
      setSessions(res.sessions)
    } catch {
      // ignore
    }
  }, [])

  const loadMessages = useCallback(async (sessionId: string) => {
    try {
      const res: MessageListResponse = await api.getMessages(sessionId) as MessageListResponse
      setMessageList(res.messages)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    if (api.getToken()) {
      api.me()
        .then((user) => setCurrentUser(user))
        .catch(() => api.logout())
    }
    loadDocuments()
    loadSessions()
  }, [loadDocuments, loadSessions])

  const handleAuthenticated = (user: User) => {
    setCurrentUser(user)
    setSelectedSessionId(null)
    setMessageList([])
    setMessages(null)
    loadDocuments()
    loadSessions()
  }

  const handleLogout = () => {
    api.logout()
    setCurrentUser(null)
    setSelectedSessionId(null)
    setMessageList([])
    setMessages(null)
    loadDocuments()
    loadSessions()
  }

  const handleSelectSession = (id: string) => {
    setSelectedSessionId(id)
    setMessages(null)
    loadMessages(id)
  }

  const handleCreateSession = async () => {
    setCreating(true)
    try {
      const session = await api.createSession() as Session
      setSessions((prev: Session[]) => [session, ...prev])
      setSelectedSessionId(session.id)
      setMessageList([])
      setMessages(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create session')
    } finally {
      setCreating(false)
    }
  }

  const handleMessageSent = (response: SendMessageResponse) => {
    setMessages(response)
    setMessageList((prev) => [
      ...prev,
      response.user_message,
      response.assistant_message,
    ])
  }

  const clearError = () => setError('')
  const selectedSession = sessions.find((session) => session.id === selectedSessionId)

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand-block">
          <span className="brand-kicker">Knowledge Workspace</span>
          <h1>Enterprise AI Agent</h1>
        </div>
        <div className="workspace-summary" aria-label="Workspace summary">
          <span>{documents.length} docs</span>
          <span>{sessions.length} sessions</span>
          <span>{currentUser ? currentUser.role : 'guest'}</span>
        </div>
        <div className="header-tools">
          <HealthStatus />
          <AuthPanel
            user={currentUser}
            onAuthenticated={handleAuthenticated}
            onLogout={handleLogout}
            onError={(msg) => setError(msg)}
          />
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError}>Dismiss</button>
        </div>
      )}

      <main className="app-main">
        <aside className="sidebar" aria-label="Workspace panels">
          <div className="sidebar-section">
            <DocumentUpload
              onUploaded={loadDocuments}
              onError={(msg) => setError(msg)}
            />
            <DocumentList
              documents={documents}
              onRefresh={loadDocuments}
              onError={(msg) => setError(msg)}
            />
          </div>
          <div className="sidebar-section">
            <ToolPanel currentUser={currentUser} onError={(msg) => setError(msg)} />
          </div>
          <div className="sidebar-section">
            <ChatSessionList
              sessions={sessions}
              selectedId={selectedSessionId}
              onSelect={handleSelectSession}
              onCreate={handleCreateSession}
              creating={creating}
            />
          </div>
        </aside>

        <section className="chat-area" aria-label="Conversation workspace">
          <div className="chat-toolbar">
            <div>
              <h2>{selectedSession ? selectedSession.title || 'Untitled session' : 'Conversation'}</h2>
              <span>{messageList.length} saved messages</span>
            </div>
            <span className={selectedSession ? 'workspace-state active' : 'workspace-state'}>
              {selectedSession ? 'Session active' : 'No session selected'}
            </span>
          </div>

          {selectedSessionId ? (
            <ChatWindow
              sessionId={selectedSessionId}
              messages={messageList}
              onMessageSent={handleMessageSent}
              onError={(msg) => setError(msg)}
            />
          ) : (
            <div className="chat-placeholder">
              <p>Select or create a session to start chatting.</p>
              <p className="hint">Use /tool &lt;name&gt; &lt;json&gt; in chat to invoke tools.</p>
            </div>
          )}

          {messages && messages.citations.length > 0 && (
            <CitationList citations={messages.citations} traceId={messages.trace_id} />
          )}
        </section>
      </main>

      {currentUser && currentUser.role === 'admin' && (
        <section className="admin-region">
          <AdminDashboard user={currentUser} />
        </section>
      )}
    </div>
  )
}
