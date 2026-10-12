import { useEffect, useState } from 'react'
import TikTokConnection from './TikTokConnection'
import MetaConnection from './MetaConnection'

type ConnectionStatus = 'checking' | 'connected' | 'disconnected'

export default function YouTubeConnection() {
  const [status, setStatus] = useState<ConnectionStatus>('checking')
  const [failed, setFailed] = useState(
    new URLSearchParams(window.location.search).get('youtube') === 'error',
  )

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/youtube/status', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Status unavailable')
        return response.json() as Promise<{ connected: boolean }>
      })
      .then((result) => setStatus(result.connected ? 'connected' : 'disconnected'))
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus('disconnected')
          setFailed(true)
        }
      })
    return () => controller.abort()
  }, [])

  return (
    <section
      className="mx-auto mt-8 max-w-[650px] rounded-2xl border border-[#e5ebf3] bg-white px-5 py-5 sm:px-7"
      aria-labelledby="connections-heading"
    >
      <h2 id="connections-heading" className="text-sm font-semibold text-ink">
        Publishing connections
      </h2>
      <div className="mt-4 flex items-center justify-between gap-4">
        <span className="text-sm font-medium text-ink">YouTube</span>
        {status === 'checking' ? (
          <span className="text-sm text-slate-500" role="status">
            Checking...
          </span>
        ) : status === 'connected' ? (
          <span className="text-sm font-semibold text-[#237653]" role="status">
            ✓ Connected
          </span>
        ) : (
          <button
            type="button"
            onClick={() => window.location.assign('http://localhost:8001/api/youtube/oauth/start')}
            className="rounded-lg border border-blue px-4 py-2 text-sm font-semibold text-blue transition-colors hover:bg-[#f5f9fe] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
          >
            Connect YouTube
          </button>
        )}
      </div>
      {failed && status !== 'connected' && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          YouTube connection failed.
        </p>
      )}
      <TikTokConnection />
      <MetaConnection />
    </section>
  )
}
