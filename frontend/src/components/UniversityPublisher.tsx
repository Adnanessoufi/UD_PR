import { useEffect, useState } from 'react'
import type { MediaAsset } from '../types/media'
import type { PublishedArticle } from '../types/universitySite'

export default function UniversityPublisher({
  runId,
  media,
  disabled,
}: {
  runId: string
  media: MediaAsset[]
  disabled: boolean
}) {
  const [article, setArticle] = useState<PublishedArticle | null>(null)
  const [checking, setChecking] = useState(true)
  const [publishing, setPublishing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/university-site/status/${runId}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Could not check the demo article status.')
        return response.json() as Promise<{ published: PublishedArticle | null }>
      })
      .then((result) => setArticle(result.published))
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error ? cause.message : 'Could not check the demo article status.',
          )
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false)
      })
    return () => controller.abort()
  }, [runId])

  async function publish() {
    setPublishing(true)
    setError('')
    try {
      const response = await fetch(`/api/university-site/publish/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          primary_media_id: media.find((item) => item.primary)?.id || null,
          media_ids: media.map((item) => item.id),
        }),
      })
      const result = (await response.json()) as PublishedArticle & { detail?: string }
      if (!response.ok) throw new Error(result.detail || 'Could not publish the demo article.')
      setArticle(result)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not publish the demo article.')
    } finally {
      setPublishing(false)
    }
  }

  return (
    <section
      className="mt-8 rounded-xl border border-[#dce6f2] bg-[#f8fbff] p-5"
      aria-label="University Website publishing"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">University Website</h3>
        <span className={`text-sm font-semibold ${article ? 'text-[#237653]' : 'text-slate-500'}`}>
          {checking ? 'Checking...' : article ? '✓ Published' : 'Ready'}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-500">Local hackathon demo website</p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {!checking && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={disabled || publishing}
            onClick={() => void publish()}
            className="rounded-lg bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#123e85] disabled:opacity-50"
          >
            {publishing
              ? 'Publishing...'
              : article
                ? 'Update article'
                : error
                  ? 'Retry publish'
                  : 'Publish to demo website'}
          </button>
          {article && (
            <a
              href={article.article_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-blue px-4 py-2.5 text-sm font-semibold text-blue hover:bg-white"
            >
              View article ↗
            </a>
          )}
        </div>
      )}
    </section>
  )
}
