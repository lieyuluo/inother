import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ToolInfo, ToolInvokeResponse } from '../types'

interface ToolPanelProps {
  onError: (msg: string) => void
}

export function ToolPanel({ onError }: ToolPanelProps) {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [selectedTool, setSelectedTool] = useState<string>('')
  const [inputText, setInputText] = useState('')
  const [result, setResult] = useState<ToolInvokeResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listTools().then((res) => {
      const tools = res.tools as ToolInfo[]
      setTools(tools)
      if (tools.length > 0) {
        setSelectedTool(tools[0].name)
      }
    }).catch(() => {
      // ignore
    })
  }, [])

  const handleInvoke = async () => {
    setLoading(true)
    setResult(null)
    try {
      let input: Record<string, unknown> = {}
      if (inputText.trim()) {
        input = JSON.parse(inputText)
      }
      const res = await api.invokeTool(selectedTool, input) as ToolInvokeResponse
      setResult(res)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Tool invocation failed')
    } finally {
      setLoading(false)
    }
  }

  const selectedToolInfo = tools.find((t) => t.name === selectedTool)

  return (
    <div className="tool-panel">
      <h3>Tools</h3>
      <div className="tool-select-row">
        <select
          value={selectedTool}
          onChange={(e) => {
            setSelectedTool(e.target.value)
            setResult(null)
          }}
        >
          {tools.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name}
            </option>
          ))}
        </select>
      </div>
      {selectedToolInfo && (
        <p className="tool-description">
          {selectedToolInfo.description}
          <span className="tool-role">Role: {selectedToolInfo.required_role}</span>
        </p>
      )}
      <div className="tool-input-row">
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder='{"text": "hello"} or {"expression": "1+2"}'
          rows={2}
        />
      </div>
      <button onClick={handleInvoke} disabled={loading || !selectedTool}>
        {loading ? 'Running...' : 'Invoke'}
      </button>
      {result && (
        <div className={`tool-result tool-result-${result.status}`}>
          <div className="tool-result-header">
            <strong>{result.tool_name}</strong>
            <span className="tool-status">{result.status}</span>
            <span className="tool-latency">{result.latency_ms.toFixed(1)}ms</span>
          </div>
          {result.output && (
            <pre className="tool-output">
              {JSON.stringify(result.output, null, 2)}
            </pre>
          )}
          {result.error && (
            <p className="tool-error-text">{result.error}</p>
          )}
        </div>
      )}
    </div>
  )
}
