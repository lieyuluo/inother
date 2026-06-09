export interface HealthResponse {
  status: string
  service: string
  version: string
}

export interface Document {
  id: string
  title: string
  filename: string
  file_type: string
  file_size: number
  status: string
  created_at: string
  updated_at: string | null
}

export interface Session {
  id: string
  title: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface Message {
  id: string
  session_id: string
  role: string
  content: string
  token_count: number | null
  created_at: string
}

export interface Citation {
  document_id: string
  document_title: string
  chunk_id: string
  chunk_index: number
  score: number
  snippet: string
}

export interface SendMessageResponse {
  user_message: Message
  assistant_message: Message
  citations: Citation[]
  trace_id: string
}

export interface SessionListResponse {
  sessions: Session[]
  total: number
}

export interface MessageListResponse {
  messages: Message[]
  total: number
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
}
