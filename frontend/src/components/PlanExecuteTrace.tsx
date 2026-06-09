import type { PlanStep, StepResult } from '../types'

interface PlanExecuteTraceProps {
  plan: PlanStep[]
  stepResults: StepResult[]
}

export function PlanExecuteTrace({ plan, stepResults }: PlanExecuteTraceProps) {
  if (!plan || plan.length === 0) return null

  // Build a map of step results by index for quick lookup
  const resultMap = new Map<number, StepResult>()
  for (const sr of stepResults) {
    resultMap.set(sr.step_index, sr)
  }

  return (
    <div className="plan-execute-trace">
      <h4>Plan &amp; Execute</h4>
      {plan.map((step) => {
        const result = resultMap.get(step.step_index)
        return (
          <div
            key={step.step_index}
            className={`plan-step plan-step-${result?.status || step.status}`}
          >
            <div className="plan-step-header">
              <span className="step-index">Step {step.step_index}</span>
              <span className={`step-status step-status-${result?.status || step.status}`}>
                {result?.status || step.status}
              </span>
              <span className="step-action-type">{step.action_type}</span>
              {step.tool_name && (
                <span className="step-tool">{step.tool_name}</span>
              )}
              {result?.latency_ms !== null && result?.latency_ms !== undefined && (
                <span className="step-latency">{result.latency_ms.toFixed(1)}ms</span>
              )}
            </div>
            <div className="plan-step-body">
              <div className="step-field">
                <strong>Description:</strong> {step.description}
              </div>
              {step.tool_name && Object.keys(step.tool_input).length > 0 && (
                <div className="step-field">
                  <strong>Input:</strong>{' '}
                  <code>{JSON.stringify(step.tool_input)}</code>
                </div>
              )}
              {result?.output && (
                <div className="step-field">
                  <strong>Output:</strong> {result.output}
                </div>
              )}
              {result?.error && (
                <div className="step-field step-field-error">
                  <strong>Error:</strong> {result.error}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
