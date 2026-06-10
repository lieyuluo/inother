import { useState } from 'react'
import { api } from '../api/client'
import type { Document } from '../types'

interface Props {
  documents: Document[]
  onRefresh: () => void
  onError: (msg: string) => void
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
  }
  return (bytes / 1024).toFixed(1) + 'KB'
}

function fileTypeLabel(fileType: string): string {
  const labels: Record<string, string> = {
    txt: 'TXT',
    md: 'MD',
    pdf: 'PDF',
    docx: 'DOCX',
  }
  return labels[fileType] || fileType.toUpperCase()
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
        <p className="empty-text">No documents yet. Upload a .txt, .md, .pdf, or .docx file.</p>
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
              <div className="doc-badges">
                <span className={`doc-status status-${doc.status}`}>{doc.status}</span>
                <span className="doc-file-type">{fileTypeLabel(doc.file_type)}</span>
                {doc.visibility === 'public' && (
                  <span className="doc-visibility doc-visibility-public">public</span>
                )}
                {doc.visibility !== 'public' && (
                  <span className="doc-visibility doc-visibility-private">private</span>
                )}
              </div>
              <span className="doc-meta">
                {formatFileSize(doc.file_size)}
                {doc.chunk_count != null && (
                  <span className="doc-chunk-count"> | {doc.chunk_count} chunks</span>
                )}
                {doc.parser_name && <> | parser: {doc.parser_name}</>}
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
