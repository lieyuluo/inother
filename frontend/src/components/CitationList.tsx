import type { Citation } from '../types'

interface Props {
  citations: Citation[]
  traceId: string
}

export function CitationList({ citations, traceId }: Props) {
  return (
    <div className="citation-list">
      <h4>
        Citations ({citations.length}) <span className="trace-id">trace: {traceId.slice(0, 8)}...</span>
      </h4>
      <ul>
        {citations.map((c, i) => (
          <li key={i} className="citation-item">
            <div className="citation-header">
              <span className="citation-title">{c.document_title}</span>
              <span className="citation-index">Chunk {c.chunk_index}</span>
              <span className="citation-score">Score: {c.score.toFixed(4)}</span>
            </div>
            <p className="citation-snippet">{c.snippet}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
