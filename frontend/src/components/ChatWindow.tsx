import { useState } from 'react'
import { api } from '../api/client'
import type { Citation, Message, PlanStep, ReActStep, SendMessageResponse, StepResult } from '../types'
import { CitationList } from './CitationList'
import { PlanExecuteTrace } from './PlanExecuteTrace'
import { ReActSteps } from './ReActSteps'

interface Props {
  sessionId: string
  messages: Message[]
  onMessageSent: (response: SendMessageResponse) => void
  onError: (msg: string) => void
}

export function ChatWindow({ sessionId, messages, onMessageSent, onError }: Props) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [lastCitations, setLastCitations] = useState<Citation[]>([])
  const [lastTraceId, setLastTraceId] = useState('')
  const [lastSteps, setLastSteps] = useState<ReActStep[] | null>(null)
  const [lastPlan, setLastPlan] = useState<PlanStep[] | null>(null)
  const [lastStepResults, setLastStepResults] = useState<StepResult[] | null>(null)
  const [mode, setMode] = useState<string>('rag')
  const [streaming, setStreaming] = useState(false)
  const [streamAnswer, setStreamAnswer] = useState('')

  const handleSend = async () => {
    const content = input.trim()
    if (!content || sending) return

    setInput('')
    setSending(true)
    setStreamAnswer('')

    if (streaming) {
      // Streaming mode
      let fullAnswer = ''
      let traceId = ''
      let citations: Citation[] = []
      let steps: ReActStep[] | null = null
      let plan: PlanStep[] | null = null
      let stepResults: StepResult[] | null = null
      let toolCalls: Record<string, unknown>[] | null = null
      let assistantMessage: Message | null = null
      let userMessage: Message | null = null

      await api.sendMessageStream(
        sessionId,
        content,
        mode,
        (event, data) => {
          switch (event) {
            case 'trace':
              traceId = (data as { trace_id: string }).trace_id
              setLastTraceId(traceId)
              break
            case 'user_message':
              userMessage = data as Message
              break
            case 'token':
              fullAnswer += (data as { content: string }).content
              setStreamAnswer(fullAnswer)
              break
            case 'citations':
              citations = data as Citation[]
              setLastCitations(citations)
              break
            case 'steps':
              steps = data as ReActStep[]
              setLastSteps(steps)
              break
            case 'plan':
              plan = data as PlanStep[]
              setLastPlan(plan)
              break
            case 'step_results':
              stepResults = data as StepResult[]
              setLastStepResults(stepResults)
              break
            case 'tool_calls':
              toolCalls = data as Record<string, unknown>[]
              break
            case 'assistant_message':
              assistantMessage = data as Message
              break
            case 'done':
              // Stream complete - notify parent
              if (userMessage && assistantMessage) {
                onMessageSent({
                  user_message: userMessage,
                  assistant_message: assistantMessage,
                  citations,
                  trace_id: traceId,
                  steps,
                  tool_calls: toolCalls,
                  mode: mode === 'rag' ? null : mode,
                  plan,
                  step_results: stepResults,
                })
              }
              setStreamAnswer('')
              break
            case 'error':
              onError((data as { error: string }).error)
              break
          }
        },
        (error) => {
          onError(error)
        },
      )
    } else {
      // Non-streaming mode
      try {
        const res = await api.sendMessage(sessionId, content, mode) as SendMessageResponse
        setLastCitations(res.citations)
        setLastTraceId(res.trace_id)
        setLastSteps(res.steps)
        setLastPlan(res.plan)
        setLastStepResults(res.step_results)
        onMessageSent(res)
      } catch (e) {
        onError(e instanceof Error ? e.message : 'Failed to send message')
      }
    }

    setSending(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <h3>No messages yet</h3>
            <p>Ask a question against your knowledge base to start this session.</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            <span className="message-role">{msg.role}</span>
            <div className="message-content">{msg.content}</div>
          </div>
        ))}
        {streamAnswer && (
          <div className="message message-assistant">
            <span className="message-role">assistant</span>
            <div className="message-content streaming">{streamAnswer}</div>
          </div>
        )}
        {sending && !streamAnswer && (
          <div className="message message-assistant">
            <span className="message-role">assistant</span>
            <div className="message-content loading">Thinking...</div>
          </div>
        )}
      </div>

      {lastPlan && lastStepResults && lastPlan.length > 0 && (
        <PlanExecuteTrace plan={lastPlan} stepResults={lastStepResults} />
      )}

      {lastSteps && lastSteps.length > 0 && (
        <ReActSteps steps={lastSteps} />
      )}

      {lastCitations.length > 0 && (
        <CitationList citations={lastCitations} traceId={lastTraceId} />
      )}

      <div className="chat-input">
        <div className="chat-input-row">
          <div className="composer-controls">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="mode-select"
              aria-label="Agent mode"
            >
              <option value="rag">RAG</option>
              <option value="react">ReAct</option>
              <option value="plan_execute">Plan-Exec</option>
            </select>
            <label className="stream-toggle">
              <input
                type="checkbox"
                checked={streaming}
                onChange={(e) => setStreaming(e.target.checked)}
              />
              Stream
            </label>
          </div>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question... (/tool for manual tool call)"
            disabled={sending}
            rows={2}
          />
          <button className="btn-primary" onClick={handleSend} disabled={sending || !input.trim()}>
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}
