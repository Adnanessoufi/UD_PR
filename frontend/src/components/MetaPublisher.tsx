import { useEffect, useState } from 'react'

type Platform = 'facebook' | 'instagram'
type Connection = { facebook_connected: boolean; instagram_connected: boolean }
type Publication = {
  success: boolean
  platform: Platform
  status: 'IDLE' | 'PROCESSING' | 'PUBLISHED'
  post_id?: string
  media_id?: string
}

export default function MetaPublisher({
  platform,
  runId,
  primaryMediaId,
  disabled,
}: {
  platform: Platform
  runId: string
  primaryMediaId: string | null
  disabled: boolean
}) {
  const [connected, setConnected] = useState<boolean | null>(null)
  const [publication, setPublication] = useState<Publication | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const label = platform === 'facebook' ? 'Facebook' : 'Instagram'

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      fetch('/api/meta/status', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error('Connection unavailable')
        return response.json() as Promise<Connection>
      }),
      fetch(`/api/meta/${platform}/publish/${runId}/status`, { signal: controller.signal }).then(
        (response) => {
          if (!response.ok) throw new Error('Publication status unavailable')
          return response.json() as Promise<Publication>
        },
      ),
    ])
      .then(([connection, saved]) => {
        setConnected(connection[`${platform}_connected`])
        setPublication(saved)
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(`${label} publishing status is unavailable.`)
      })
    return () => controller.abort()
  }, [platform, runId, label])

  useEffect(() => {
    if (platform !== 'instagram' || publication?.status !== 'PROCESSING' || busy || error) return
    const timer = window.setTimeout(() => void publish(), 3000)
    return () => window.clearTimeout(timer)
  }, [platform, publication?.status, busy, error])

  async function publish() {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/meta/${platform}/publish/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primary_media_id: primaryMediaId }),
      })
      const result = (await response.json()) as Publication & {
        detail?: string | { message?: string; meta_message?: string }
      }
      if (!response.ok) {
        const detail = result.detail
        const message = typeof detail === 'object' ? detail.meta_message || detail.message : detail
        throw new Error(message || `${label} publishing failed.`)
      }
      setPublication(result)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `${label} publishing failed.`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className="mt-8 rounded-xl border border-[#dce6f2] bg-[#f8fbff] p-5"
      aria-label={`${label} publishing`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">{label}</h3>
        <span
          className={`text-sm ${connected ? 'font-semibold text-[#237653]' : 'text-slate-500'}`}
        >
          {connected === null
            ? 'Checking connection...'
            : connected
              ? '✓ Connected'
              : 'Not configured'}
        </span>
      </div>
      {publication?.success ? (
        <p className="mt-4 text-sm font-semibold text-[#237653]">✓ Published to {label}</p>
      ) : busy ? (
        <p role="status" className="mt-4 text-sm font-medium text-blue">
          {publication?.status === 'PROCESSING'
            ? 'Processing media...'
            : `Publishing to ${label}...`}
        </p>
      ) : (
        <div className="mt-4">
          {publication?.status === 'PROCESSING' && (
            <p role="status" className="mb-3 text-sm text-slate-600">
              Instagram is processing the selected media. Check status to continue publishing.
            </p>
          )}
          {error && (
            <p role="alert" className="mb-3 text-sm text-red-700">
              {error}
            </p>
          )}
          {connected && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => void publish()}
              className="rounded-lg bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#123e85] disabled:opacity-50"
            >
              {publication?.status === 'PROCESSING'
                ? 'Check status'
                : error
                  ? 'Retry'
                  : `Publish to ${label}`}
            </button>
          )}
          {connected === false && (
            <p className="text-sm text-slate-500">
              Configure {label} publishing on the backend to continue.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
