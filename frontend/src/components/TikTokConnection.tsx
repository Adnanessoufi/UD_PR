import { useEffect, useState } from 'react'

type ConnectionStatus = 'checking' | 'connected' | 'disconnected'

export default function TikTokConnection() {
  const callbackResult = new URLSearchParams(window.location.search).get('tiktok')
  const [status, setStatus] = useState<ConnectionStatus>('checking')
  const [failed, setFailed] = useState(callbackResult === 'error')

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/tiktok/status', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Status unavailable')
        return response.json() as Promise<{ connected: boolean }>
      })
      .then((result) => {
        setStatus(result.connected ? 'connected' : 'disconnected')
        if (!result.connected && callbackResult === 'connected') setFailed(true)
        if (result.connected) setFailed(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus('disconnected')
          setFailed(true)
        }
      })
    return () => controller.abort()
  }, [callbackResult])

  return (
    <div className="mt-4 border-t border-[#e5ebf3] pt-4">
      <div className="flex items-center justify-between gap-4">
        <span className="text-sm font-medium text-ink">TikTok</span>
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
            onClick={() => window.location.assign('http://localhost:8001/api/tiktok/oauth/start')}
            className="rounded-lg border border-blue px-4 py-2 text-sm font-semibold text-blue transition-colors hover:bg-[#f5f9fe] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
          >
            {failed ? 'Retry' : 'Connect TikTok'}
          </button>
        )}
      </div>
      {failed && status !== 'connected' && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          TikTok connection failed.
        </p>
      )}
    </div>
  )
}
