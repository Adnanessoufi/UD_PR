import { useEffect, useState } from 'react'
import { collectFeeds, getNewsInbox, importArticle } from '../services/campaigns'
import type { NewsInbox } from '../types/campaign'
import type { UploadResult } from '../types/upload'
export default function NewsPanel({
  onCollected,
}: {
  onCollected: (source: UploadResult) => void
}) {
  const [url, setUrl] = useState('')
  const [feeds, setFeeds] = useState('')
  const [inbox, setInbox] = useState<NewsInbox | null>(null)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    void getNewsInbox()
      .then((result) => {
        if (alive) {
          setInbox(result)
          setFeeds(result.feeds.join('\n'))
        }
      })
      .catch((cause) => {
        if (alive) setError(cause instanceof Error ? cause.message : 'Could not load news.')
      })
    return () => {
      alive = false
    }
  }, [])
  async function collect(articleUrl: string) {
    setBusy(true)
    setError('')
    try {
      onCollected(await importArticle(articleUrl.trim()))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not collect article.')
    } finally {
      setBusy(false)
    }
  }
  async function refresh() {
    const urls = feeds
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    if (!urls.length || urls.length > 5) {
      setError('Enter between one and five feed URLs, one per line.')
      return
    }
    setBusy(true)
    setError('')
    try {
      setInbox(await collectFeeds(urls))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not collect feed.')
    } finally {
      setBusy(false)
    }
  }
  const items = (inbox?.items || []).filter((item) =>
    `${item.title} ${item.summary}`.toLowerCase().includes(query.toLowerCase()),
  )
  return (
    <section className="ud-source-section sprint-news">
      <h2>Collect news</h2>
      <p className="ud-source-note">
        Import a public article or collect RSS/Atom stories. Choose a story to turn it into a
        campaign.
      </p>
      <label>
        Article URL
        <div className="sprint-inline-actions">
          <input
            aria-label="Article URL"
            type="url"
            placeholder="https://…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button
            type="button"
            className="ud-secondary-button"
            disabled={busy || !url.trim()}
            onClick={() => void collect(url)}
          >
            Collect article
          </button>
        </div>
      </label>
      <details>
        <summary>RSS / Atom feeds</summary>
        <label>
          Feed URLs, one per line
          <textarea
            rows={3}
            aria-label="Feed URLs"
            placeholder="Add up to five public HTTPS feeds"
            value={feeds}
            onChange={(e) => setFeeds(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="ud-secondary-button"
          disabled={busy || !feeds.trim()}
          onClick={() => void refresh()}
        >
          Collect latest stories
        </button>
      </details>
      {busy && <p role="status">Collecting source…</p>}
      {error && (
        <p className="ud-error" role="alert">
          {error}
        </p>
      )}
      {inbox?.added !== undefined && (
        <p className="ud-source-note">
          {inbox.added} new stories collected. Duplicate URLs are kept once.
        </p>
      )}
      {inbox?.errors?.map((item) => (
        <p key={item.url} className="ud-error">
          {item.url}: {item.message}
        </p>
      ))}
      {!!inbox?.items.length && (
        <>
          <input
            aria-label="Search collected news"
            className="sprint-news-search"
            placeholder="Filter collected stories…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="sprint-news-list">
            {items.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.summary}</p>
                  <a href={item.url} target="_blank" rel="noopener noreferrer">
                    Read original ↗
                  </a>
                </div>
                <button
                  type="button"
                  className="ud-secondary-button"
                  disabled={busy}
                  onClick={() => void collect(item.url)}
                >
                  Use story
                </button>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
