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

  const handleSend = async () => {
    const content = input.trim()
    if (!content || sending) return

    setInput('')
    setSending(true)
    try {
      const res = await api.sendMessage(sessionId, content, mode)
      setLastCitations(res.citations)
      setLastTraceId(res.trace_id)
      setLastSteps(res.steps)
      setLastPlan(res.plan)
      setLastStepResults(res.step_results)
      onMessageSent(res)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to send message')
    } finally {
      setSending(false)
    }
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
          <p className="empty-text">No messages yet. Ask a question!</p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            <span className="message-role">{msg.role}</span>
            <div className="message-content">{msg.content}</div>
          </div>
        ))}
        {sending && (
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
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className="mode-select"
          >
            <option value="rag">RAG</option>
            <option value="react">ReAct</option>
            <option value="plan_execute">Plan-Exec</option>
          </select>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question... (/tool for manual tool call)"
            disabled={sending}
            rows={2}
          />
          <button onClick={handleSend} disabled={sending || !input.trim()}>
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}
