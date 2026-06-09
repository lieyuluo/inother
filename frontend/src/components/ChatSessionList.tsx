import type { Session } from '../types'

interface Props {
  sessions: Session[]
  selectedId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
  creating: boolean
}

export function ChatSessionList({ sessions, selectedId, onSelect, onCreate, creating }: Props) {
  return (
    <div className="session-list">
      <div className="session-header">
        <h3>Sessions</h3>
        <button onClick={onCreate} disabled={creating}>
          {creating ? '...' : '+ New'}
        </button>
      </div>
      {sessions.length === 0 && (
        <p className="empty-text">No sessions yet. Create one to start chatting.</p>
      )}
      <ul>
        {sessions.map((s) => (
          <li
            key={s.id}
            className={s.id === selectedId ? 'session-item active' : 'session-item'}
            onClick={() => onSelect(s.id)}
          >
            <span className="session-title">{s.title || 'Untitled'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
