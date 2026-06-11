import { useState } from 'react'
import { api } from '../api/client'
import type { User } from '../types'

interface AuthPanelProps {
  user: User | null
  onAuthenticated: (user: User) => void
  onLogout: () => void
  onError: (msg: string) => void
}

export function AuthPanel({ user, onAuthenticated, onLogout, onError }: AuthPanelProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    try {
      if (mode === 'register') {
        await api.register({
          email,
          username,
          password,
          full_name: fullName || undefined,
        })
      }
      const res = await api.login(email, password)
      onAuthenticated(res.user)
      setPassword('')
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  if (user) {
    return (
      <div className="auth-panel auth-panel-signed-in">
        <div className="auth-user">
          <span className="auth-name">{user.username}</span>
          <span className="auth-meta">{user.email} | {user.role}</span>
        </div>
        <button className="btn-quiet" onClick={onLogout}>Logout</button>
      </div>
    )
  }

  return (
    <div className="auth-panel">
      <div className="auth-tabs">
        <button
          className={mode === 'login' ? 'active' : ''}
          onClick={() => setMode('login')}
          type="button"
        >
          Login
        </button>
        <button
          className={mode === 'register' ? 'active' : ''}
          onClick={() => setMode('register')}
          type="button"
        >
          Register
        </button>
      </div>
      <input
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="email@example.com"
        type="email"
      />
      {mode === 'register' && (
        <>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username"
          />
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Full name"
          />
        </>
      )}
      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="password"
        type="password"
      />
      <button onClick={submit} disabled={loading || !email || !password}>
        {loading ? 'Working...' : mode === 'login' ? 'Login' : 'Register'}
      </button>
    </div>
  )
}
