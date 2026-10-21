import { useEffect, useState } from 'react'
import { listCampaigns, updateCampaign } from '../services/campaigns'
import type { CampaignSummary } from '../types/campaign'
const states: Record<string, string> = {
  draft: 'Draft',
  source_ready: 'Source collected',
  analyzed: 'Source analyzed',
  preferences_changed: 'Brief updated',
  unchecked: 'Awaiting check',
  verified: 'Ready for approval',
  needs_review: 'Needs review',
  approved: 'Approved',
}
export default function CampaignLibrary({
  onOpen,
  onClose,
}: {
  onOpen: (id: string) => Promise<void>
  onClose: () => void
}) {
  const [items, setItems] = useState<CampaignSummary[]>([])
  const [query, setQuery] = useState('')
  const [archived, setArchived] = useState(false)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [rename, setRename] = useState<string | null>(null)
  const [name, setName] = useState('')
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [onClose])
  useEffect(() => {
    let alive = true
    setBusy(true)
    setError('')
    const timer = window.setTimeout(() => {
      void listCampaigns(query, archived)
        .then((result) => {
          if (alive) setItems(result)
        })
        .catch((cause) => {
          if (alive) setError(cause instanceof Error ? cause.message : 'Could not load campaigns.')
        })
        .finally(() => {
          if (alive) setBusy(false)
        })
    }, 150)
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [query, archived, revision])
  async function change(
    item: CampaignSummary,
    changes: Partial<{ name: string; archived: boolean; starred: boolean }>,
  ) {
    setBusy(true)
    setError('')
    try {
      await updateCampaign(item, changes)
      setRename(null)
      setRevision((v) => v + 1)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update campaign.')
      setBusy(false)
    }
  }
  async function open(id: string) {
    setBusy(true)
    setError('')
    try {
      await onOpen(id)
      onClose()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not reopen campaign.')
      setBusy(false)
    }
  }
  return (
    <div
      className="workspace-modal"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="campaign-library-title"
        className="workspace-library"
      >
        <header>
          <div>
            <p className="ud-eyebrow">Workspace</p>
            <h2 id="campaign-library-title">Your campaigns</h2>
            <p>Pick up where you left off, or keep a useful draft for later.</p>
          </div>
          <button type="button" className="ud-secondary-button" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="workspace-library-filters">
          <input
            aria-label="Search campaigns"
            placeholder="Search by title or source…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <label>
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => setArchived(e.target.checked)}
            />
            Archived
          </label>
        </div>
        {error && (
          <p role="alert" className="ud-error">
            {error}
          </p>
        )}
        {busy && <p role="status">Loading campaigns…</p>}
        {!busy && !items.length && <p>No campaigns found. Add a source to start one.</p>}
        <div className="workspace-campaign-list">
          {items.map((item) => (
            <article key={item.run_id}>
              <div className="workspace-campaign-top">
                <button
                  className="workspace-star"
                  type="button"
                  aria-label={`${item.starred ? 'Unstar' : 'Star'} ${item.title}`}
                  disabled={busy}
                  onClick={() => void change(item, { starred: !item.starred })}
                >
                  {item.starred ? '★' : '☆'}
                </button>
                <div>
                  <h3>{item.title}</h3>
                  <p>
                    {item.source_kind.toUpperCase()} · {item.language.toUpperCase()} ·{' '}
                    {new Date(item.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="workspace-status">{states[item.status] || 'Draft'}</span>
              </div>
              {rename === item.run_id && (
                <div className="workspace-inline-actions">
                  <input
                    aria-label="Campaign name"
                    maxLength={140}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                  <button
                    type="button"
                    className="ud-secondary-button"
                    disabled={busy || !name.trim()}
                    onClick={() => void change(item, { name: name.trim() })}
                  >
                    Save name
                  </button>
                  <button type="button" className="ud-text-button" onClick={() => setRename(null)}>
                    Cancel
                  </button>
                </div>
              )}
              <div className="workspace-inline-actions">
                <button
                  type="button"
                  className="ud-secondary-button"
                  disabled={busy}
                  onClick={() => void open(item.run_id)}
                >
                  Open campaign
                </button>
                <button
                  type="button"
                  className="ud-text-button"
                  onClick={() => {
                    setRename(item.run_id)
                    setName(item.title)
                  }}
                >
                  Rename
                </button>
                <button
                  type="button"
                  className="ud-text-button"
                  disabled={busy}
                  onClick={() => void change(item, { archived: !item.archived })}
                >
                  {item.archived ? 'Restore' : 'Archive'}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
