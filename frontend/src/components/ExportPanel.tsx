import { useState } from 'react'
import type { PlatformResult } from '../types/platform'
export default function ExportPanel({
  runId,
  preview,
}: {
  runId: string
  preview: PlatformResult
}) {
  const [message, setMessage] = useState('')
  async function copy() {
    try {
      await navigator.clipboard.writeText(
        preview.items
          .map((p) => `[${p.platform.toUpperCase()}]\n${p.title}\n\n${p.body}`)
          .join('\n\n'),
      )
      setMessage('Platform copy copied.')
    } catch {
      setMessage('Clipboard access was unavailable. Download the text package instead.')
    }
  }
  return (
    <section className="workspace-export">
      <div>
        <h2>Take the campaign with you</h2>
        <p>
          Download your drafts to share or work on later. You'll still need approval before
          publishing through the app.
        </p>
      </div>
      <div className="workspace-inline-actions">
        <button type="button" className="ud-secondary-button" onClick={() => void copy()}>
          Copy platform text
        </button>
        <a
          className="ud-secondary-button"
          href={`/api/campaigns/${runId}/export?include_media=false`}
          download
        >
          Download text package
        </a>
        <a
          className="ud-secondary-button"
          href={`/api/campaigns/${runId}/export?include_media=true`}
          download
        >
          Download with media
        </a>
      </div>
      {message && (
        <p role="status" className="ud-source-note">
          {message}
        </p>
      )}
    </section>
  )
}
