import { useRef, useState } from 'react'
import { api } from '../api/client'

interface Props {
  onUploaded: () => void
  onError: (msg: string) => void
}

export function DocumentUpload({ onUploaded, onError }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) return

    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext !== 'txt' && ext !== 'md') {
      onError('Only .txt and .md files are supported')
      return
    }

    setUploading(true)
    try {
      await api.uploadDocument(file)
      onUploaded()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="document-upload">
      <h3>Upload Document</h3>
      <div className="upload-row">
        <input type="file" ref={fileRef} accept=".txt,.md" disabled={uploading} />
        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </div>
    </div>
  )
}
