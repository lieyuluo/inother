import type { ReActStep } from '../types'

interface ReActStepsProps {
  steps: ReActStep[]
}

export function ReActSteps({ steps }: ReActStepsProps) {
  if (!steps || steps.length === 0) return null

  return (
    <div className="react-steps">
      <h4>ReAct Steps</h4>
      {steps.map((step) => (
        <div key={step.step_index} className={`react-step react-step-${step.status}`}>
          <div className="react-step-header">
            <span className="step-index">Step {step.step_index}</span>
            <span className={`step-status step-status-${step.status}`}>
              {step.status}
            </span>
            {step.tool_name && (
              <span className="step-tool">{step.tool_name}</span>
            )}
            {step.latency_ms !== null && (
              <span className="step-latency">{step.latency_ms.toFixed(1)}ms</span>
            )}
          </div>
          <div className="react-step-body">
            <div className="step-field">
              <strong>Thought:</strong> {step.thought}
            </div>
            <div className="step-field">
              <strong>Action:</strong> {step.action}
            </div>
            {Object.keys(step.action_input).length > 0 && (
              <div className="step-field">
                <strong>Input:</strong>{' '}
                <code>{JSON.stringify(step.action_input)}</code>
              </div>
            )}
            {step.observation && (
              <div className="step-field">
                <strong>Observation:</strong> {step.observation}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
