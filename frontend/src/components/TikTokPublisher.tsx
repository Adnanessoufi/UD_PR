import { useEffect, useState } from 'react'

type Publication = {
  success: boolean
  platform: 'tiktok'
  publish_id?: string
  status: string
  privacy: 'SELF_ONLY'
}

function isProcessing(status: string | undefined) {
  return status === 'PROCESSING_UPLOAD' || status === 'PROCESSING_DOWNLOAD'
}

export default function TikTokPublisher({ runId, disabled }: { runId: string; disabled: boolean }) {
  const [connected, setConnected] = useState<boolean | null>(null)
  const [publication, setPublication] = useState<Publication | null>(null)
  const [busy, setBusy] = useState<'publishing' | 'checking' | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      fetch('/api/tiktok/status', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error('Connection unavailable')
        return response.json() as Promise<{ connected: boolean }>
      }),
      fetch(`/api/tiktok/publish/${runId}`, { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error('Publishing status unavailable')
        return response.json() as Promise<Publication>
      }),
    ])
      .then(([connection, saved]) => {
        setConnected(connection.connected)
        if (saved.status !== 'IDLE') setPublication(saved)
        if (saved.status === 'FAILED' || saved.status === 'UPLOAD_FAILED') setFailed(true)
      })
      .catch(() => {
        if (!controller.signal.aborted) setConnected(false)
      })
    return () => controller.abort()
  }, [runId])

  async function request(path: string, action: 'publishing' | 'checking') {
    setBusy(action)
    setFailed(false)
    try {
      const response = await fetch(path, { method: 'POST' })
      const result = (await response.json()) as Publication
      if (!response.ok) throw new Error('TikTok request failed')
      setPublication(result)
      if (result.status === 'FAILED' || result.status === 'UPLOAD_FAILED') setFailed(true)
    } catch {
      setFailed(true)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section
      className="mt-8 rounded-xl border border-[#dce6f2] bg-[#f8fbff] p-5"
      aria-labelledby="tiktok-publishing-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="tiktok-publishing-heading" className="text-sm font-semibold text-ink">
          TikTok
        </h3>
        {connected === null ? (
          <span className="text-sm text-slate-500">Checking connection...</span>
        ) : connected ? (
          <span className="text-sm font-semibold text-[#237653]">✓ Connected</span>
        ) : (
          <span className="text-sm text-slate-500">Not connected</span>
        )}
      </div>
      {publication?.status === 'PUBLISH_COMPLETE' ? (
        <div className="mt-4 space-y-2 text-sm">
          <p className="font-semibold text-[#237653]">✓ Published to TikTok</p>
          <p className="text-slate-500">Private</p>
        </div>
      ) : busy ? (
        <p role="status" className="mt-4 text-sm font-medium text-blue">
          {busy === 'publishing' ? 'Publishing to TikTok...' : 'Checking TikTok status...'}
        </p>
      ) : connected && failed ? (
        <div className="mt-4">
          <p role="alert" className="text-sm text-red-700">
            TikTok publishing failed.
          </p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => void request(`/api/tiktok/publish/${runId}`, 'publishing')}
            className="mt-3 rounded-lg bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#123e85] disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      ) : connected && isProcessing(publication?.status) ? (
        <div className="mt-4">
          <p className="text-sm text-slate-600">TikTok is still processing...</p>
          <button
            type="button"
            onClick={() => void request(`/api/tiktok/publish/${runId}/status`, 'checking')}
            className="mt-3 rounded-lg border border-blue px-4 py-2.5 text-sm font-semibold text-blue hover:bg-white"
          >
            Check status
          </button>
        </div>
      ) : connected ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => void request(`/api/tiktok/publish/${runId}`, 'publishing')}
          className="mt-4 rounded-lg bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#123e85] disabled:opacity-50"
        >
          Publish to TikTok
        </button>
      ) : connected === false ? (
        <p className="mt-3 text-sm text-slate-500">
          Connect TikTok from the start page to publish this video.
        </p>
      ) : null}
    </section>
  )
}
