import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { HealthResponse } from '../types'

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <div className="health-status">
      {error && <span className="status-error">API Error: {error}</span>}
      {health && (
        <span className={health.status === 'ok' ? 'status-ok' : 'status-error'}>
          {health.status === 'ok' ? 'API Online' : 'API Offline'} | v{health.version}
        </span>
      )}
      {!health && !error && <span className="status-loading">Checking...</span>}
    </div>
  )
}
