import { useEffect, useState } from 'react'

type Status = { facebook_connected: boolean; instagram_connected: boolean }

export default function MetaConnection() {
  const [status, setStatus] = useState<Status | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/meta/status', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Meta status unavailable')
        return response.json() as Promise<Status>
      })
      .then(setStatus)
      .catch(() => {
        if (!controller.signal.aborted)
          setStatus({ facebook_connected: false, instagram_connected: false })
      })
    return () => controller.abort()
  }, [])

  return (
    <div className="mt-4 space-y-3 border-t border-[#edf1f6] pt-4">
      {(['facebook', 'instagram'] as const).map((platform) => (
        <div key={platform} className="flex items-center justify-between gap-4">
          <span className="text-sm font-medium text-ink">
            {platform === 'facebook' ? 'Facebook Page' : 'Instagram'}
          </span>
          <span
            className={`text-sm ${status?.[`${platform}_connected`] ? 'font-semibold text-[#237653]' : 'text-slate-500'}`}
          >
            {status === null
              ? 'Checking...'
              : status[`${platform}_connected`]
                ? '✓ Connected'
                : 'Not configured'}
          </span>
        </div>
      ))}
    </div>
  )
}
