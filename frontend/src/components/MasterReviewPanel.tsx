import { useState } from 'react'
import type { MasterContent } from '../types/content'
type Props = {
  content: MasterContent
  onSave: (content: MasterContent) => Promise<void>
  onEditingChange: (editing: boolean) => void
}
export default function MasterReviewPanel({ content, onSave, onEditingChange }: Props) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<MasterContent | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const fields: {
    key: 'headline' | 'lead' | 'body' | 'short_summary' | 'press_release'
    label: string
  }[] = [
    { key: 'headline', label: 'Headline' },
    { key: 'lead', label: 'Lead' },
    { key: 'body', label: 'Master story' },
    { key: 'short_summary', label: 'Short summary' },
    { key: 'press_release', label: 'Press release' },
  ]
  function edit() {
    setDraft({ ...content, key_messages: [...content.key_messages] })
    setError('')
    onEditingChange(true)
  }
  function cancel() {
    setDraft(null)
    setError('')
    onEditingChange(false)
  }
  async function save() {
    if (!draft) return
    setSaving(true)
    setError('')
    try {
      await onSave(draft)
      setDraft(null)
      onEditingChange(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save the master story.')
    } finally {
      setSaving(false)
    }
  }
  return (
    <section className="ud-master-review">
      <button
        type="button"
        className="ud-secondary-button"
        onClick={() => setOpen((value) => !value)}
        disabled={!!draft}
      >
        {open ? 'Hide master story & press release' : 'Review master story & press release'}
      </button>
      {open && (
        <div className="ud-master-content">
          <h2>Master story & press release</h2>
          <p>
            These drafts are checked along with your channel posts. If you edit them, run the check
            again and approve the new version.
          </p>
          {error && (
            <p className="ud-error" role="alert">
              {error}
            </p>
          )}
          {fields.map((field) => (
            <div key={field.key} className="ud-master-field">
              <label>{field.label}</label>
              {draft ? (
                <textarea
                  aria-label={field.label}
                  rows={field.key === 'press_release' || field.key === 'body' ? 8 : 3}
                  value={draft[field.key]}
                  disabled={saving}
                  onChange={(event) =>
                    setDraft((current) =>
                      current ? { ...current, [field.key]: event.target.value } : current,
                    )
                  }
                />
              ) : (
                <p>{content[field.key]}</p>
              )}
            </div>
          ))}
          <div className="ud-master-field">
            <label>Key messages</label>
            {draft ? (
              <textarea
                aria-label="Key messages, one per line"
                rows={4}
                value={draft.key_messages.join('\n')}
                disabled={saving}
                onChange={(event) =>
                  setDraft((current) =>
                    current
                      ? { ...current, key_messages: event.target.value.split('\n') }
                      : current,
                  )
                }
              />
            ) : (
              <ul>
                {content.key_messages.map((message, index) => (
                  <li key={index}>{message}</li>
                ))}
              </ul>
            )}
          </div>
          {draft ? (
            <div className="ud-master-actions">
              <button
                type="button"
                className="ud-primary-button"
                disabled={saving}
                onClick={() => void save()}
              >
                {saving ? 'Saving…' : 'Save master content'}
              </button>
              <button
                type="button"
                className="ud-secondary-button"
                disabled={saving}
                onClick={cancel}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button type="button" className="ud-secondary-button" onClick={edit}>
              Edit master content
            </button>
          )}
        </div>
      )}
    </section>
  )
}
