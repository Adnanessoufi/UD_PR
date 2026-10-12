import { useEffect, useState } from 'react'
import type { PublishedArticle, PublishedMedia } from '../types/universitySite'

const demoNotice = 'Hackathon demo — not the official University of Debrecen website'

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? ''
    : new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'long', year: 'numeric' }).format(
        date,
      )
}

function SiteHeader() {
  return (
    <>
      <div className="ud-demo-banner">{demoNotice}</div>
      <div className="ud-utility">
        <div className="ud-site-container ud-utility-inner">
          <span>University news · English</span>
          <span className="ud-utility-right">
            Debrecen, Hungary <span aria-hidden="true">│</span> EN
          </span>
        </div>
      </div>
      <header className="ud-header">
        <div className="ud-site-container ud-header-inner">
          <a
            href="/university-news"
            className="ud-brand"
            aria-label="University of Debrecen demo news home"
          >
            <img className="ud-site-logo" src="/ud-logo.png" alt="" aria-hidden="true" />
            <span className="ud-brand-copy">
              <strong>UNIVERSITY OF DEBRECEN</strong>
              <small>NEWS &amp; STORIES</small>
            </span>
          </a>
          <div className="ud-header-aside">
            Knowledge for the future <span className="ud-header-rule" />
          </div>
        </div>
        <nav className="ud-nav" aria-label="University navigation">
          <div className="ud-site-container ud-nav-inner">
            <span>UNIVERSITY</span>
            <span>EDUCATION</span>
            <span>RESEARCH</span>
            <span>INTERNATIONAL</span>
            <a href="/university-news" aria-current="page">
              NEWS
            </a>
            <span>CONTACT</span>
          </div>
        </nav>
      </header>
    </>
  )
}

function SiteFooter() {
  return (
    <footer className="ud-footer">
      <div className="ud-site-container ud-footer-main">
        <div>
          <p className="ud-footer-kicker">UNIVERSITY OF DEBRECEN</p>
          <p className="ud-footer-title">Knowledge, research and community.</p>
          <p className="ud-footer-location">Debrecen, Hungary</p>
        </div>
        <div className="ud-footer-links">
          <a href="/university-news">News</a>
          <span>Education</span>
          <span>Research</span>
          <span>International</span>
        </div>
      </div>
      <div className="ud-footer-bottom">
        <div className="ud-site-container">
          <span>{demoNotice}</span>
          <span>Local university news demonstration</span>
        </div>
      </div>
    </footer>
  )
}

function ArticleMedia({ media, hero = false }: { media: PublishedMedia; hero?: boolean }) {
  return (
    <figure className={hero ? 'ud-hero-media' : 'ud-gallery-item'} data-media-id={media.id}>
      {media.media_type === 'video' ? (
        <video src={media.url} controls preload="metadata" playsInline aria-label={media.label} />
      ) : (
        <img src={media.url} alt={media.label} loading={hero ? 'eager' : 'lazy'} />
      )}
      {media.label && <figcaption>{media.label}</figcaption>}
    </figure>
  )
}

function ArticleView({ article }: { article: PublishedArticle }) {
  const paragraphs = article.body
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean)
  useEffect(() => {
    document.title = `${article.headline} | University of Debrecen demo news`
  }, [article.headline])
  return (
    <>
      <section className="ud-page-intro">
        <div className="ud-site-container">
          <div className="ud-breadcrumb">
            <a href="/university-news">News</a>
            <span aria-hidden="true">›</span>
            <span>{article.category}</span>
          </div>
        </div>
      </section>
      <main className="ud-article-main">
        <article>
          <div className="ud-site-container ud-article-heading">
            <p className="ud-category">
              <span className="ud-category-line" />
              {article.category}
            </p>
            <h1>{article.headline}</h1>
            <div className="ud-article-meta">
              <time dateTime={article.published_at}>{formatDate(article.published_at)}</time>
              <span aria-hidden="true" className="ud-meta-dot" />
              <span>University News</span>
            </div>
          </div>
          {article.primary_media && (
            <div className="ud-site-container">
              <ArticleMedia media={article.primary_media} hero />
            </div>
          )}
          <div className="ud-site-container ud-article-grid">
            <div className="ud-article-copy">
              <p className="ud-article-lead">{article.lead}</p>
              {paragraphs.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
              {article.remaining_media.length > 0 && (
                <section className="ud-article-gallery" aria-label="Article media gallery">
                  <div className="ud-section-heading">
                    <span /> <h2>More from this story</h2>
                  </div>
                  <div className="ud-gallery-grid">
                    {article.remaining_media.map((media) => (
                      <ArticleMedia key={media.id} media={media} />
                    ))}
                  </div>
                </section>
              )}
            </div>
            <aside className="ud-article-sidebar">
              <div className="ud-sidebar-card">
                <span className="ud-sidebar-label">ARTICLE DETAILS</span>
                <p>
                  <strong>Published</strong>
                  <br />
                  {formatDate(article.published_at)}
                </p>
                <p>
                  <strong>Category</strong>
                  <br />
                  {article.category}
                </p>
                {article.source_title && (
                  <p>
                    <strong>Source publication</strong>
                    <br />
                    {article.source_title}
                  </p>
                )}
              </div>
            </aside>
          </div>
        </article>
        <div className="ud-site-container ud-back-news">
          <a href="/university-news">
            <span aria-hidden="true">←</span> Back to News
          </a>
        </div>
      </main>
    </>
  )
}

function NewsList({ articles }: { articles: PublishedArticle[] }) {
  useEffect(() => {
    document.title = 'News | University of Debrecen demo'
  }, [])
  return (
    <main className="ud-site-container ud-news-main">
      <div className="ud-breadcrumb">
        <span>Home</span>
        <span aria-hidden="true">›</span>
        <span>News</span>
      </div>
      <p className="ud-category">
        <span className="ud-category-line" />
        UNIVERSITY NEWS
      </p>
      <h1>News</h1>
      <p className="ud-news-intro">Stories from the University of Debrecen.</p>
      {articles.length === 0 ? (
        <p className="ud-empty">No demo articles have been published yet.</p>
      ) : (
        <div className="ud-news-grid">
          {articles.map((article) => (
            <a key={article.slug} href={article.article_url} className="ud-news-card">
              <div className="ud-news-thumb">
                {article.primary_media?.media_type === 'image' ? (
                  <img src={article.primary_media.url} alt="" loading="lazy" />
                ) : article.primary_media?.media_type === 'video' ? (
                  <video src={article.primary_media.url} preload="metadata" muted />
                ) : (
                  <span>UD</span>
                )}
              </div>
              <div className="ud-news-card-content">
                <p>
                  {article.category} <span>·</span> {formatDate(article.published_at)}
                </p>
                <h2>{article.headline}</h2>
                <span className="ud-read-more">
                  Read article <span aria-hidden="true">→</span>
                </span>
              </div>
            </a>
          ))}
        </div>
      )}
    </main>
  )
}

export default function UniversityNewsPage() {
  const path = window.location.pathname.replace(/\/+$/, '')
  const slug = path.startsWith('/university-news/')
    ? decodeURIComponent(path.slice('/university-news/'.length))
    : null
  const [article, setArticle] = useState<PublishedArticle | null>(null)
  const [articles, setArticles] = useState<PublishedArticle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetch(
      slug
        ? `/api/university-site/articles/${encodeURIComponent(slug)}`
        : '/api/university-site/articles',
      { signal: controller.signal },
    )
      .then((response) => {
        if (!response.ok) throw new Error('This demo article could not be found.')
        return response.json()
      })
      .then((result) => {
        if (slug) setArticle(result as PublishedArticle)
        else setArticles(result as PublishedArticle[])
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error ? cause.message : 'The demo news page could not be loaded.',
          )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [slug])

  return (
    <div className="ud-site">
      <SiteHeader />
      {loading ? (
        <main className="ud-site-container ud-message" role="status">
          Loading university news...
        </main>
      ) : error ? (
        <main className="ud-site-container ud-message">
          <h1>Article unavailable</h1>
          <p>{error}</p>
          <a href="/university-news">View all news</a>
        </main>
      ) : article ? (
        <ArticleView article={article} />
      ) : (
        <NewsList articles={articles} />
      )}
      <SiteFooter />
    </div>
  )
}
