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

export interface ReActStep {
  step_index: number
  thought: string
  action: string
  action_input: Record<string, unknown>
  observation: string
  status: string
  tool_name: string | null
  latency_ms: number | null
}

export interface PlanStep {
  step_index: number
  description: string
  action_type: string
  tool_name: string | null
  tool_input: Record<string, unknown>
  status: string
}

export interface StepResult {
  step_index: number
  status: string
  output: string
  error: string | null
  latency_ms: number | null
  tool_name: string | null
  citations: Record<string, unknown>[]
}

export interface SendMessageResponse {
  user_message: Message
  assistant_message: Message
  citations: Citation[]
  trace_id: string
  steps: ReActStep[] | null
  tool_calls: Record<string, unknown>[] | null
  mode: string | null
  plan: PlanStep[] | null
  step_results: StepResult[] | null
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

export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  role: 'user' | 'admin'
  is_active: boolean
  created_at: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
  full_name?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

// Tool types
export interface ToolInfo {
  name: string
  description: string
  input_schema: Record<string, unknown>
  requires_confirmation: boolean
  required_role: 'user' | 'admin'
}

export interface ToolListResponse {
  tools: ToolInfo[]
  total: number
}

export interface ToolInvokeResponse {
  tool_name: string
  status: string
  output: Record<string, unknown> | null
  error: string | null
  latency_ms: number
  trace_id: string
}
