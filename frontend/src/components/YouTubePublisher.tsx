import { useEffect, useState } from 'react'

type Publication = {
  success: boolean
  video_id?: string
  watch_url?: string
  privacy_status?: string
}

export default function YouTubePublisher({
  runId,
  title,
  description,
  disabled,
}: {
  runId: string
  title: string
  description: string
  disabled: boolean
}) {
  const [connected, setConnected] = useState<boolean | null>(null)
  const [publication, setPublication] = useState<Publication | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      fetch('/api/youtube/status', { signal: controller.signal }).then(
        (response) => response.json() as Promise<{ connected: boolean }>,
      ),
      fetch(`/api/youtube/publish/${runId}/status`, { signal: controller.signal }).then(
        (response) => response.json() as Promise<Publication>,
      ),
    ])
      .then(([connection, saved]) => {
        setConnected(connection.connected)
        if (saved.success) setPublication(saved)
      })
      .catch(() => {
        if (!controller.signal.aborted) setConnected(false)
      })
    return () => controller.abort()
  }, [runId])

  async function publish() {
    setPublishing(true)
    setFailed(false)
    try {
      const response = await fetch(`/api/youtube/publish/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description }),
      })
      const result = (await response.json()) as Publication
      if (!response.ok || !result.success) throw new Error('Publish failed')
      setPublication(result)
    } catch {
      setFailed(true)
    } finally {
      setPublishing(false)
    }
  }

  return (
    <section
      className="mt-8 rounded-xl border border-[#dce6f2] bg-[#f8fbff] p-5"
      aria-labelledby="youtube-publishing-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="youtube-publishing-heading" className="text-sm font-semibold text-ink">
          YouTube
        </h3>
        {connected === null ? (
          <span className="text-sm text-slate-500">Checking connection...</span>
        ) : connected ? (
          <span className="text-sm font-semibold text-[#237653]">✓ Connected</span>
        ) : (
          <span className="text-sm text-slate-500">Not connected</span>
        )}
      </div>
      {publication?.success ? (
        <div className="mt-4 space-y-2 text-sm">
          <p className="font-semibold text-[#237653]">✓ Published to YouTube</p>
          <p className="text-slate-500">Private</p>
          {publication.watch_url && (
            <a
              href={publication.watch_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block font-semibold text-blue hover:underline"
            >
              Open video
            </a>
          )}
        </div>
      ) : connected ? (
        <div className="mt-4">
          {publishing ? (
            <p role="status" className="text-sm font-medium text-blue">
              Publishing to YouTube...
            </p>
          ) : (
            <button
              type="button"
              disabled={disabled}
              onClick={() => void publish()}
              className="rounded-lg bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#123e85] disabled:opacity-50"
            >
              {failed ? 'Retry' : 'Publish to YouTube'}
            </button>
          )}
          {failed && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              YouTube publishing failed.
            </p>
          )}
        </div>
      ) : connected === false ? (
        <p className="mt-3 text-sm text-slate-500">
          Connect YouTube from the start page to publish this video.
        </p>
      ) : null}
    </section>
  )
}
