import { useState } from 'react'
import { api } from '../api/client'
import type { Document } from '../types'

interface Props {
  documents: Document[]
  onRefresh: () => void
  onError: (msg: string) => void
}

export function DocumentList({ documents, onRefresh, onError }: Props) {
  const [deleting, setDeleting] = useState<string | null>(null)

  const handleDelete = async (id: string) => {
    setDeleting(id)
    try {
      await api.deleteDocument(id)
      onRefresh()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  if (documents.length === 0) {
    return (
      <div className="document-list">
        <h3>Documents</h3>
        <p className="empty-text">No documents yet. Upload a .txt or .md file.</p>
      </div>
    )
  }

  return (
    <div className="document-list">
      <h3>Documents ({documents.length})</h3>
      <ul>
        {documents.map((doc) => (
          <li key={doc.id} className="document-item">
            <div className="doc-info">
              <span className="doc-title">{doc.title}</span>
              <span className={`doc-status status-${doc.status}`}>{doc.status}</span>
              <span className="doc-meta">
                {doc.file_type} | {(doc.file_size / 1024).toFixed(1)}KB
              </span>
            </div>
            <button
              className="btn-delete"
              onClick={() => handleDelete(doc.id)}
              disabled={deleting === doc.id}
            >
              {deleting === doc.id ? '...' : 'Delete'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
