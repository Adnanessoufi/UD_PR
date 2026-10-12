import { useEffect, useState } from 'react'
import type { MediaAsset } from '../types/media'
import type { PlatformName, PlatformResult } from '../types/platform'

type Destination = 'facebook' | 'instagram' | 'tiktok' | 'youtube' | 'website'
type PublishState = 'checking' | 'ready' | 'publishing' | 'published' | 'failed'
type Row = { state: PublishState; error?: string; url?: string; linkError?: string }
const order: Destination[] = ['facebook', 'instagram', 'tiktok', 'youtube', 'website']
const labels: Record<Destination, string> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  website: 'University Website',
}

async function jsonResponse(response: Response): Promise<Record<string, unknown>> {
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>
  if (!response.ok) {
    const detail = data.detail
    const message =
      typeof detail === 'string'
        ? detail
        : typeof detail === 'object' && detail !== null
          ? String(
              (detail as Record<string, unknown>).meta_message ||
                (detail as Record<string, unknown>).message ||
                '',
            )
          : ''
    throw new Error(message || `Publishing request failed (${response.status}).`)
  }
  return data
}

const pause = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

async function publishDestination(
  destination: Destination,
  runId: string,
  preview: PlatformResult,
  media: MediaAsset[],
): Promise<string | undefined> {
  const primary = media.find((item) => item.primary)?.id || null
  if (destination === 'website') {
    const result = await jsonResponse(
      await fetch(`/api/university-site/publish/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          primary_media_id: primary,
          media_ids: media.map((item) => item.id),
        }),
      }),
    )
    return typeof result.article_url === 'string' ? result.article_url : undefined
  }
  if (destination === 'youtube') {
    const post = preview.items.find((item) => item.platform === 'youtube')
    const result = await jsonResponse(
      await fetch(`/api/youtube/publish/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: post?.title || '', description: post?.body || '' }),
      }),
    )
    if (!result.success) throw new Error('YouTube publishing failed.')
    return typeof result.watch_url === 'string' ? result.watch_url : undefined
  }
  if (destination === 'tiktok') {
    let result = await jsonResponse(await fetch(`/api/tiktok/publish/${runId}`, { method: 'POST' }))
    for (
      let attempt = 0;
      attempt < 30 && ['PROCESSING_UPLOAD', 'PROCESSING_DOWNLOAD'].includes(String(result.status));
      attempt++
    ) {
      await pause(3000)
      result = await jsonResponse(
        await fetch(`/api/tiktok/publish/${runId}/status`, { method: 'POST' }),
      )
    }
    if (result.status !== 'PUBLISH_COMPLETE')
      throw new Error(
        `TikTok publishing ${String(result.status || 'did not complete').toLowerCase()}.`,
      )
    return undefined
  }
  let result = await jsonResponse(
    await fetch(`/api/meta/${destination}/publish/${runId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ primary_media_id: primary }),
    }),
  )
  if (destination === 'instagram') {
    for (let attempt = 0; attempt < 30 && result.status === 'PROCESSING'; attempt++) {
      await pause(3000)
      result = await jsonResponse(
        await fetch(`/api/meta/instagram/publish/${runId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ primary_media_id: primary }),
        }),
      )
    }
  }
  if (!result.success && result.status !== 'PUBLISHED')
    throw new Error(`${labels[destination]} publishing did not complete.`)
  try {
    const status = await jsonResponse(
      await fetch(`/api/meta/${destination}/publish/${runId}/status`),
    )
    return typeof status.publication_url === 'string' ? status.publication_url : undefined
  } catch {
    // The post succeeded; a link lookup must not change its publishing state.
    return undefined
  }
}

async function savedPublication(destination: Destination, runId: string): Promise<Row> {
  try {
    const path =
      destination === 'website'
        ? `/api/university-site/status/${runId}`
        : destination === 'tiktok'
          ? `/api/tiktok/publish/${runId}`
          : destination === 'youtube'
            ? `/api/youtube/publish/${runId}/status`
            : `/api/meta/${destination}/publish/${runId}/status`
    const data = await jsonResponse(await fetch(path))
    if (destination === 'website' && data.published) {
      const article = data.published as Record<string, unknown>
      return {
        state: 'published',
        url: typeof article.article_url === 'string' ? article.article_url : undefined,
      }
    }
    if (destination === 'tiktok' && data.status === 'PUBLISH_COMPLETE')
      return { state: 'published' }
    if (destination === 'youtube' && data.success)
      return {
        state: 'published',
        url: typeof data.watch_url === 'string' ? data.watch_url : undefined,
      }
    if (
      (destination === 'facebook' || destination === 'instagram') &&
      (data.success || data.status === 'PUBLISHED')
    ) {
      return {
        state: 'published',
        url: typeof data.publication_url === 'string' ? data.publication_url : undefined,
        linkError:
          typeof data.publication_link_error === 'string' ? data.publication_link_error : undefined,
      }
    }
  } catch {
    /* A status check must never trigger a publishing request. */
  }
  return { state: 'ready' }
}

export default function PublishPanel({
  runId,
  preview,
  media,
  approved = false,
}: {
  runId: string
  preview: PlatformResult
  media: MediaAsset[]
  approved?: boolean
}) {
  const captionOnlyTikTok =
    preview.platforms.includes('tiktok') && !preview.content_types.includes('video')
  const destinations = order.filter(
    (item) =>
      preview.platforms.includes(item as PlatformName) && !(item === 'tiktok' && captionOnlyTikTok),
  )
  const [rows, setRows] = useState<Partial<Record<Destination, Row>>>({})
  const [tiktokProfileUrl, setTiktokProfileUrl] = useState<string>()

  useEffect(() => {
    if (!destinations.includes('tiktok')) return
    let active = true
    void fetch('/api/tiktok/status')
      .then(jsonResponse)
      .then((data) => {
        if (active && typeof data.profile_url === 'string') setTiktokProfileUrl(data.profile_url)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [runId, preview])

  useEffect(() => {
    let active = true
    void Promise.all(
      destinations.map(
        async (destination) => [destination, await savedPublication(destination, runId)] as const,
      ),
    ).then((entries) => {
      if (active) setRows(Object.fromEntries(entries) as Partial<Record<Destination, Row>>)
    })
    return () => {
      active = false
    }
  }, [runId, preview])

  async function publish(destination: Destination) {
    if (!approved) return
    setRows((current) => ({ ...current, [destination]: { state: 'publishing' } }))
    try {
      const url = await publishDestination(destination, runId, preview, media)
      const refreshed =
        destination === 'instagram' && !url ? await savedPublication(destination, runId) : undefined
      setRows((current) => ({
        ...current,
        [destination]: refreshed?.state === 'published' ? refreshed : { state: 'published', url },
      }))
    } catch (cause) {
      setRows((current) => ({
        ...current,
        [destination]: {
          state: 'failed',
          error: cause instanceof Error ? cause.message : 'Publishing failed.',
        },
      }))
    }
  }

  function publishAll() {
    void Promise.allSettled(
      destinations
        .filter(
          (destination) =>
            rows[destination]?.state !== 'published' && rows[destination]?.state !== 'publishing',
        )
        .map(publish),
    )
  }

  const states = destinations.map((destination) => rows[destination]?.state || 'checking')
  const failed = states.filter((state) => state === 'failed').length
  const allPublished = states.length > 0 && states.every((state) => state === 'published')
  const anyPublishing = states.includes('publishing')
  const checking = states.includes('checking')
  const heading = allPublished
    ? 'Published successfully'
    : failed && !anyPublishing
      ? `Published with ${failed} issue${failed === 1 ? '' : 's'}`
      : 'Ready to publish'
  return (
    <section className="ud-publish" aria-label="Publish package">
      <div className="ud-section-heading">
        <p className="ud-eyebrow">04 / Publish</p>
        <h1>{heading}</h1>
        <p>Each destination publishes independently. Review the result for every channel.</p>
      </div>
      {!approved && (
        <p role="status" className="ud-error">
          Return to review, check the current package and save human approval before publishing.
        </p>
      )}
      {captionOnlyTikTok && (
        <p className="ud-source-note">
          TikTok caption preview only. A video is required to publish there.
        </p>
      )}
      <div className="ud-publish-list">
        {destinations.map((destination) => {
          const row: Row = rows[destination] || { state: 'checking' }
          return (
            <div className="ud-publish-row" key={destination}>
              <div>
                <strong>{labels[destination]}</strong>
                {row.error && <small role="alert">{row.error}</small>}
                {row.url && (
                  <a href={row.url} target="_blank" rel="noopener noreferrer">
                    View publication ↗
                  </a>
                )}
                {row.linkError && <small role="status">{row.linkError}</small>}
                {destination === 'tiktok' && row.state === 'published' && tiktokProfileUrl && (
                  <a href={tiktokProfileUrl} target="_blank" rel="noopener noreferrer">
                    Open TikTok account ↗
                  </a>
                )}
              </div>
              <span className={`ud-publish-state ${row.state}`}>
                {row.state === 'checking'
                  ? 'Checking...'
                  : row.state === 'publishing'
                    ? 'Publishing...'
                    : row.state === 'published'
                      ? 'Published'
                      : row.state === 'failed'
                        ? 'Failed'
                        : 'Ready'}
              </span>
              {row.state !== 'published' && (
                <button
                  type="button"
                  className="ud-row-button"
                  disabled={!approved || row.state === 'checking' || row.state === 'publishing'}
                  onClick={() => void publish(destination)}
                >
                  {row.state === 'failed' ? 'Retry' : 'Publish'}
                </button>
              )}
            </div>
          )
        })}
      </div>
      <button
        type="button"
        className="ud-primary-button ud-publish-all"
        disabled={
          !approved || allPublished || anyPublishing || checking || destinations.length === 0
        }
        onClick={publishAll}
      >
        Publish all
      </button>
    </section>
  )
}
