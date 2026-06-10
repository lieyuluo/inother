import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type {
  AdminOverview,
  AdminUser,
  AdminDocument,
  AdminTool,
  MCPServerStatus,
  AdminConfig,
  AdminMetrics,
  AuditLogEntry,
  User,
} from '../types'

interface AdminDashboardProps {
  user: User | null
}

type AdminTab = 'overview' | 'users' | 'documents' | 'audit' | 'tools' | 'mcp' | 'config' | 'metrics'

export function AdminDashboard({ user }: AdminDashboardProps) {
  const [activeTab, setActiveTab] = useState<AdminTab>('overview')
  const [error, setError] = useState('')

  if (!user || user.role !== 'admin') {
    return <div className="admin-error">Admin access required</div>
  }

  const tabs: { key: AdminTab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'users', label: 'Users' },
    { key: 'documents', label: 'Documents' },
    { key: 'audit', label: 'Audit Logs' },
    { key: 'tools', label: 'Tools' },
    { key: 'mcp', label: 'MCP Servers' },
    { key: 'config', label: 'Config' },
    { key: 'metrics', label: 'Metrics' },
  ]

  return (
    <div className="admin-dashboard">
      <h2>Admin Dashboard</h2>
      <div className="admin-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? 'admin-tab active' : 'admin-tab'}
            onClick={() => { setActiveTab(tab.key); setError('') }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {error && <div className="admin-error">{error}</div>}
      <div className="admin-content">
        {activeTab === 'overview' && <OverviewTab onError={setError} />}
        {activeTab === 'users' && <UsersTab onError={setError} />}
        {activeTab === 'documents' && <DocumentsTab onError={setError} />}
        {activeTab === 'audit' && <AuditTab onError={setError} />}
        {activeTab === 'tools' && <ToolsTab onError={setError} />}
        {activeTab === 'mcp' && <McpTab onError={setError} />}
        {activeTab === 'config' && <ConfigTab onError={setError} />}
        {activeTab === 'metrics' && <MetricsTab onError={setError} />}
      </div>
    </div>
  )
}

// Overview Tab
function OverviewTab({ onError }: { onError: (msg: string) => void }) {
  const [data, setData] = useState<AdminOverview | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await api.getAdminOverview()
      setData(res)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to load overview')
    }
  }, [onError])

  useEffect(() => { load() }, [load])

  if (!data) return <div>Loading...</div>

  return (
    <div className="admin-overview">
      <div className="admin-stat-grid">
        <div className="admin-stat"><span className="stat-value">{data.users_count}</span><span className="stat-label">Users</span></div>
        <div className="admin-stat"><span className="stat-value">{data.documents_count}</span><span className="stat-label">Documents</span></div>
        <div className="admin-stat"><span className="stat-value">{data.chat_sessions_count}</span><span className="stat-label">Sessions</span></div>
        <div className="admin-stat"><span className="stat-value">{data.messages_count}</span><span className="stat-label">Messages</span></div>
        <div className="admin-stat"><span className="stat-value">{data.audit_logs_count}</span><span className="stat-label">Audit Logs</span></div>
        <div className="admin-stat"><span className="stat-value">{data.tools_count}</span><span className="stat-label">Tools</span></div>
        <div className="admin-stat"><span className="stat-value">{data.mcp_servers_count}</span><span className="stat-label">MCP Servers</span></div>
        <div className="admin-stat"><span className="stat-value">{data.system_status}</span><span className="stat-label">Status</span></div>
      </div>
    </div>
  )
}

// Users Tab
function UsersTab({ onError }: { onError: (msg: string) => void }) {
  const [users, setUsers] = useState<AdminUser[]>([])

  const load = useCallback(async () => {
    try {
      const res = await api.getAdminUsers()
      setUsers(res.users)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to load users')
    }
  }, [onError])

  useEffect(() => { load() }, [load])

  const toggleActive = async (userId: string, currentActive: boolean) => {
    try {
      await api.patchAdminUser(userId, { is_active: !currentActive })
      load()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to update user')
    }
  }

  const toggleRole = async (userId: string, currentRole: string) => {
    try {
      await api.patchAdminUser(userId, { role: currentRole === 'admin' ? 'user' : 'admin' })
      load()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to update user')
    }
  }

  return (
    <div className="admin-users">
      <table className="admin-table">
        <thead>
          <tr><th>Email</th><th>Username</th><th>Role</th><th>Active</th><th>Created</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.email}</td>
              <td>{u.username}</td>
              <td><span className={`role-badge ${u.role}`}>{u.role}</span></td>
              <td>{u.is_active ? 'Yes' : 'No'}</td>
              <td>{new Date(u.created_at).toLocaleDateString()}</td>
              <td>
                <button onClick={() => toggleActive(u.id, u.is_active)} className="btn-sm">
                  {u.is_active ? 'Disable' : 'Enable'}
                </button>
                <button onClick={() => toggleRole(u.id, u.role)} className="btn-sm">
                  {u.role === 'admin' ? 'Demote' : 'Promote'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Documents Tab
function DocumentsTab({ onError }: { onError: (msg: string) => void }) {
  const [docs, setDocs] = useState<AdminDocument[]>([])

  const load = useCallback(async () => {
    try {
      const res = await api.getAdminDocuments()
      setDocs(res.documents)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to load documents')
    }
  }, [onError])

  useEffect(() => { load() }, [load])

  return (
    <div className="admin-documents">
      <table className="admin-table">
        <thead>
          <tr><th>Title</th><th>Type</th><th>Owner</th><th>Visibility</th><th>Status</th><th>Chunks</th></tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.title}</td>
              <td>{d.file_type}</td>
              <td>{d.owner_email || d.user_id}</td>
              <td><span className={`vis-badge ${d.visibility}`}>{d.visibility}</span></td>
              <td>{d.status}</td>
              <td>{d.chunk_count ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Audit Tab
function AuditTab({ onError }: { onError: (msg: string) => void }) {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [actionFilter, setActionFilter] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.getAdminAuditLogs(actionFilter || undefined)
      setLogs(res.logs)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to load audit logs')
    }
  }, [onError, actionFilter])

  useEffect(() => { load() }, [load])

  return (
    <div className="admin-audit">
      <div className="audit-filter">
        <input
          type="text"
          placeholder="Filter by action (e.g., rag.query)"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        />
        <button onClick={load}>Refresh</button>
      </div>
      <table className="admin-table">
        <thead>
          <tr><th>Time</th><th>Action</th><th>Actor</th><th>Resource</th><th>User ID</th></tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{new Date(log.created_at).toLocaleString()}</td>
              <td>{log.action}</td>
              <td>{log.actor}</td>
              <td>{log.resource_type || '-'}</td>
              <td>{log.user_id || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Tools Tab
function ToolsTab({ onError }: { onError: (msg: string) => void }) {
  const [tools, setTools] = useState<AdminTool[]>([])

  useEffect(() => {
    api.getAdminTools()
      .then((res) => setTools(res.tools))
      .catch((e) => onError(e instanceof Error ? e.message : 'Failed to load tools'))
  }, [onError])

  return (
    <div className="admin-tools">
      <table className="admin-table">
        <thead>
          <tr><th>Name</th><th>Source</th><th>Role</th><th>Enabled</th><th>Server</th><th>Transport</th></tr>
        </thead>
        <tbody>
          {tools.map((t) => (
            <tr key={t.name}>
              <td title={t.description}>{t.name}</td>
              <td>{t.source || '-'}</td>
              <td><span className={`role-badge ${t.required_role}`}>{t.required_role}</span></td>
              <td>{t.enabled ? 'Yes' : 'No'}</td>
              <td>{t.server_name || '-'}</td>
              <td>{t.transport || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// MCP Tab
function McpTab({ onError }: { onError: (msg: string) => void }) {
  const [servers, setServers] = useState<MCPServerStatus[]>([])

  useEffect(() => {
    api.getAdminMcpServers()
      .then((res) => setServers(res.servers))
      .catch((e) => onError(e instanceof Error ? e.message : 'Failed to load MCP servers'))
  }, [onError])

  return (
    <div className="admin-mcp">
      <table className="admin-table">
        <thead>
          <tr><th>Name</th><th>Transport</th><th>Enabled</th><th>Status</th><th>Tools</th><th>Role</th></tr>
        </thead>
        <tbody>
          {servers.map((s) => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td>{s.transport}</td>
              <td>{s.enabled ? 'Yes' : 'No'}</td>
              <td><span className={`status-badge ${s.status}`}>{s.status}</span></td>
              <td>{s.tool_count}</td>
              <td>{s.required_role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Config Tab
function ConfigTab({ onError }: { onError: (msg: string) => void }) {
  const [config, setConfig] = useState<AdminConfig | null>(null)

  useEffect(() => {
    api.getAdminConfig()
      .then((res) => setConfig(res))
      .catch((e) => onError(e instanceof Error ? e.message : 'Failed to load config'))
  }, [onError])

  if (!config) return <div>Loading...</div>

  return (
    <div className="admin-config">
      <table className="admin-table">
        <tbody>
          {Object.entries(config).map(([key, value]) => (
            <tr key={key}><td className="config-key">{key}</td><td>{String(value)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Metrics Tab
function MetricsTab({ onError }: { onError: (msg: string) => void }) {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await api.getAdminMetrics()
      setMetrics(res)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to load metrics')
    }
  }, [onError])

  useEffect(() => { load() }, [load])

  if (!metrics) return <div>Loading...</div>

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return `${h}h ${m}m`
  }

  return (
    <div className="admin-metrics">
      <div className="admin-stat-grid">
        <div className="admin-stat"><span className="stat-value">{metrics.chat_messages_total}</span><span className="stat-label">Messages</span></div>
        <div className="admin-stat"><span className="stat-value">{metrics.rag_queries_total}</span><span className="stat-label">RAG Queries</span></div>
        <div className="admin-stat"><span className="stat-value">{metrics.tool_invocations_total}</span><span className="stat-label">Tool Calls</span></div>
        <div className="admin-stat"><span className="stat-value">{metrics.react_runs_total}</span><span className="stat-label">ReAct Runs</span></div>
        <div className="admin-stat"><span className="stat-value">{metrics.plan_execute_runs_total}</span><span className="stat-label">Plan-Exec Runs</span></div>
        <div className="admin-stat"><span className="stat-value">{metrics.documents_total}</span><span className="stat-label">Documents</span></div>
        <div className="admin-stat"><span className="stat-value">{metrics.audit_logs_total}</span><span className="stat-label">Audit Logs</span></div>
        <div className="admin-stat"><span className="stat-value">{formatUptime(metrics.uptime_seconds)}</span><span className="stat-label">Uptime</span></div>
      </div>
      <button onClick={load} className="btn-sm" style={{ marginTop: '12px' }}>Refresh</button>
    </div>
  )
}
