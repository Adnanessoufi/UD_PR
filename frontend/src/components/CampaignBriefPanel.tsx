import { useEffect, useState } from 'react'
import type { CampaignBrief } from '../types/campaign'
export default function CampaignBriefPanel({
  brief,
  disabled,
  onSave,
}: {
  brief: CampaignBrief
  disabled: boolean
  onSave: (brief: CampaignBrief) => Promise<void>
}) {
  const [draft, setDraft] = useState(brief)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    setDraft(brief)
    setError('')
  }, [brief])
  const changed = JSON.stringify(draft) !== JSON.stringify(brief)
  async function save() {
    setBusy(true)
    setError('')
    try {
      await onSave(draft)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save the brief.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="ud-source-section ud-brief">
      <h2>Campaign brief</h2>
      <p className="ud-source-note">
        Set the audience and style once. Each channel adapts the same source facts.
      </p>
      <fieldset disabled={disabled || busy} className="workspace-brief-grid">
        <label>
          Audience
          <select
            value={draft.audience}
            onChange={(e) =>
              setDraft({ ...draft, audience: e.target.value as CampaignBrief['audience'] })
            }
          >
            <option value="general_public">General public</option>
            <option value="students">Students</option>
            <option value="industry">Industry partners</option>
            <option value="researchers">Researchers</option>
          </select>
        </label>
        <label>
          Tone
          <select
            value={draft.tone}
            onChange={(e) => setDraft({ ...draft, tone: e.target.value as CampaignBrief['tone'] })}
          >
            <option value="institutional">Institutional</option>
            <option value="friendly">Friendly</option>
            <option value="energetic">Energetic</option>
          </select>
        </label>
        <label>
          Length
          <select
            value={draft.length}
            onChange={(e) =>
              setDraft({ ...draft, length: e.target.value as CampaignBrief['length'] })
            }
          >
            <option value="short">Short</option>
            <option value="standard">Standard</option>
            <option value="detailed">Detailed</option>
          </select>
        </label>
        <label className="workspace-wide">
          Communication focus
          <input
            maxLength={300}
            value={draft.focus}
            onChange={(e) => setDraft({ ...draft, focus: e.target.value })}
            placeholder="What should this campaign help people understand?"
          />
        </label>
        <label className="workspace-wide">
          Call to action
          <input
            maxLength={200}
            value={draft.call_to_action}
            onChange={(e) => setDraft({ ...draft, call_to_action: e.target.value })}
            placeholder="For example: read the full study"
          />
        </label>
      </fieldset>
      {error && (
        <p role="alert" className="ud-error">
          {error}
        </p>
      )}
      <div className="workspace-inline-actions">
        <button
          type="button"
          className="ud-secondary-button"
          disabled={disabled || busy || !changed}
          onClick={() => void save()}
        >
          {busy ? 'Saving…' : 'Save brief'}
        </button>
        {changed && (
          <span className="ud-source-note">
            Save before generating. Updated preferences require new content and review.
          </span>
        )}
      </div>
    </section>
  )
}
