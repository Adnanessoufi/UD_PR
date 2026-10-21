import { useEffect, useState } from 'react'
import { useJob } from '../hooks/useJob'
import { request } from '../services/content'
import type { MasterContent } from '../types/content'
import type { OutputLanguage } from '../types/platform'
import './story-room.css'

type Evidence = { excerpt: string; page: number | null; url: string | null; source_type: string }
type Answer = {
  id: string
  question: string
  language: OutputLanguage
  status: 'answered' | 'not_in_source'
  answer: string
  short_reply: string
  caveat: string
  evidence: Evidence[]
  excerpts_confirmed: boolean
}
const copy = {
  en: {
    eyebrow: 'Questions about the story',
    title: 'Ask this story',
    intro: 'Ask a question about the story. You can check the source excerpts behind the answer.',
    story: 'The story',
    sourceEmpty: 'Ask a question to see the source excerpts used in the answer.',
    pipeline: 'Original source → AI answer → independent check → exact excerpts',
    language: 'Answer in',
    placeholder: 'What would you like to know about this story?',
    ask: 'Ask the source',
    source: 'Inside the source',
    empty: 'Start with a question',
    emptyBody:
      'Try one of the questions below, or write your own. Check what the source can actually support.',
    chips: [
      'What is the main finding in plain language?',
      'What does the biggest improvement actually measure?',
      'What does this source not prove?',
    ],
    caveat: 'Keep in mind',
    reply: 'Reply to your audience',
    copy: 'Copy reply draft',
    copied: 'Copied',
    recent: 'Previous questions',
    confirmed: 'Exact source excerpts confirmed',
    missing: "The source doesn't back this up",
    page: 'Page',
    open: 'Open original page',
    closePage: 'Close page',
    busy: 'Preparing an answer and checking it against the source…',
    close: 'Close audience preview',
    draft: 'Audience preview · AI answer · Review replies before posting',
    noEvidence: 'No relevant evidence found in this source.',
  },
  hu: {
    eyebrow: 'Egy történet, amellyel beszélgethetsz',
    title: 'Kérdezz a történetről',
    intro: 'Lépj túl a főcímen. Kérdezz, és nézd meg az eredeti bizonyítékokat.',
    story: 'A történet',
    sourceEmpty: 'Kérdezz, és nézd meg a választ alátámasztó forrásrészleteket.',
    pipeline: 'Eredeti forrás → MI-válasz → független ellenőrzés → pontos idézetek',
    language: 'Válasz nyelve',
    placeholder: 'Mit szeretnél megtudni a történetről?',
    ask: 'Kérdezd a forrást',
    source: 'Az eredeti forrás',
    empty: 'A te kérdésed. Az eredeti bizonyíték.',
    emptyBody:
      'Válassz egy kérdést, vagy írd be a sajátodat. A válaszok a kutatás korlátait is figyelembe veszik.',
    chips: [
      'Mi a legfontosabb eredmény közérthetően?',
      'Mit mér valójában a legnagyobb javulás?',
      'Mit nem bizonyít ez a forrás?',
    ],
    caveat: 'Ezt is érdemes tudni',
    reply: 'Válasz a közönségednek',
    copy: 'Választervezet másolása',
    copied: 'Másolva',
    recent: 'Korábbi kérdések',
    confirmed: 'Az idézetek megtalálhatók a forrásban',
    missing: 'A forrás ezt nem támasztja alá',
    page: 'Oldal',
    open: 'Eredeti oldal megnyitása',
    closePage: 'Oldal bezárása',
    busy: 'A forrás olvasása, válaszadás és ellenőrzés…',
    close: 'Közönségnézet bezárása',
    draft: 'Közönségnézet · MI-válasz · Közzététel előtt ellenőrizd a válaszokat',
    noEvidence: 'Ebben a forrásban nincs releváns bizonyíték.',
  },
}

export default function StoryRoom({
  runId,
  story,
  language: initialLanguage,
  demoAnswers,
}: {
  runId: string
  story: MasterContent
  language: OutputLanguage
  demoAnswers?: Record<OutputLanguage, { question: string; answer: string; excerpt: string }[]>
}) {
  const [open, setOpen] = useState(false)
  const [language, setLanguage] = useState<OutputLanguage>(initialLanguage)
  const [question, setQuestion] = useState('')
  const [answers, setAnswers] = useState<Answer[]>([])
  const [selected, setSelected] = useState<Answer | null>(null)
  const [page, setPage] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)
  const [loadError, setLoadError] = useState('')
  const { job, error, pending, start } = useJob<Answer>(demoAnswers ? null : runId, 'story.answer')
  const busy = pending || job?.state === 'queued' || job?.state === 'running'
  const t = copy[language]
  const answer = selected?.language === language ? selected : null

  useEffect(() => {
    if (!open) return
    setLoadError('')
    setSelected(null)
    setAnswers([])
    setPage(null)
    setQuestion('')
    if (demoAnswers) return
    const controller = new AbortController()
    void request<Answer[]>(`/api/story-room/${runId}/answers`, 'GET', undefined, {
      signal: controller.signal,
    })
      .then(setAnswers)
      .catch((cause) => {
        if (!controller.signal.aborted)
          setLoadError(cause instanceof Error ? cause.message : 'Could not load saved questions.')
      })
    return () => controller.abort()
  }, [runId, open, Boolean(demoAnswers)])
  useEffect(() => {
    if (job?.state === 'ready' && job.result) {
      const result = job.result
      setSelected(result)
      setPage(null)
      setAnswers((previous) => [result, ...previous.filter((item) => item.id !== result.id)])
    }
  }, [job?.id, job?.state, job?.result])
  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (page !== null) setPage(null)
        else setOpen(false)
      }
    }
    window.addEventListener('keydown', escape)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener('keydown', escape)
    }
  }, [open, page])

  async function ask(value: string) {
    if (busy || value.trim().length < 5) return
    setLoadError('')
    setQuestion(value)
    setSelected(null)
    setPage(null)
    setCopied(false)
    if (demoAnswers) {
      const prepared = demoAnswers[language].find(
        (item) => item.question.toLowerCase() === value.trim().toLowerCase(),
      )
      if (!prepared) {
        setLoadError(
          language === 'en'
            ? 'This demo has prepared answers. Choose one of the sample questions below.'
            : 'A bemutató előre elkészített válaszokat tartalmaz. Válassz egy mintakérdést.',
        )
        return
      }
      const result: Answer = {
        id: `sample-${demoAnswers[language].indexOf(prepared)}`,
        question: prepared.question,
        language,
        status: 'answered',
        answer: prepared.answer,
        short_reply: prepared.answer,
        caveat:
          language === 'en'
            ? 'Prepared answer from a fictional source. No live AI check.'
            : 'Előre elkészített válasz kitalált forrásból. Nincs élő MI-ellenőrzés.',
        evidence: [{ excerpt: prepared.excerpt, page: null, url: null, source_type: 'user' }],
        excerpts_confirmed: false,
      }
      setSelected(result)
      setAnswers((previous) => [
        result,
        ...previous.filter((item) => item.id !== result.id || item.language !== language),
      ])
      return
    }
    try {
      await start({ question: value.trim(), language })
    } catch {
      /* The job hook displays the error. */
    }
  }
  function chooseLanguage(value: OutputLanguage) {
    setLanguage(value)
    setQuestion('')
    setSelected(null)
    setPage(null)
    setCopied(false)
  }
  async function copyReply() {
    if (!answer) return
    try {
      await navigator.clipboard.writeText(answer.short_reply)
      setCopied(true)
    } catch {
      setLoadError('Copy is unavailable. Select the reply text below to copy it.')
    }
  }
  return (
    <>
      <section className="story-room-invite">
        <span className="story-room-orbit" aria-hidden="true">
          ✦
        </span>
        <div>
          <span className="story-room-kicker">Questions from readers</span>
          <h3>What might people ask about this?</h3>
          <p>Try a question and see an answer with excerpts from the source.</p>
        </div>
        <button type="button" onClick={() => setOpen(true)}>
          Open audience preview <span aria-hidden="true">↗</span>
        </button>
      </section>
      {open && (
        <div
          className="story-room-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="story-room-title"
        >
          <header className="story-room-topbar">
            <a href="#" onClick={(event) => event.preventDefault()} className="story-room-brand">
              <img src="/ud-logo.png" alt="University of Debrecen" />
              <span>
                UD <strong>Living Stories</strong>
              </span>
            </a>
            <button
              type="button"
              className="story-room-close"
              onClick={() => setOpen(false)}
              aria-label={t.close}
            >
              ×
            </button>
          </header>
          <main className="story-room-content">
            <div className="story-room-heading">
              <p className="story-room-kicker">✦ {t.eyebrow}</p>
              <h1 id="story-room-title">
                {t.title}
                <span>.</span>
              </h1>
              <p>{t.intro}</p>
            </div>
            <article className="story-room-story">
              <span className="story-room-kicker">{t.story}</span>
              <h2>{story.headline}</h2>
              <p>{story.short_summary}</p>
            </article>
            <div className="story-room-toolbar">
              <span>{t.language}</span>
              <div role="group" aria-label="Answer language">
                <button
                  type="button"
                  aria-pressed={language === 'en'}
                  disabled={busy}
                  onClick={() => chooseLanguage('en')}
                >
                  English
                </button>
                <button
                  type="button"
                  aria-pressed={language === 'hu'}
                  disabled={busy}
                  onClick={() => chooseLanguage('hu')}
                >
                  Magyar
                </button>
              </div>
            </div>
            <div className="story-room-grid">
              <section className="story-room-conversation" aria-label="Ask the original source">
                <form
                  className="story-room-question"
                  onSubmit={(event) => {
                    event.preventDefault()
                    void ask(question)
                  }}
                >
                  <label className="sr-only" htmlFor="story-question">
                    {t.placeholder}
                  </label>
                  <textarea
                    id="story-question"
                    rows={2}
                    maxLength={600}
                    value={question}
                    disabled={busy}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder={t.placeholder}
                    autoFocus
                  />
                  <button type="submit" disabled={busy || question.trim().length < 5}>
                    {busy ? '…' : t.ask} <span aria-hidden="true">↗</span>
                  </button>
                </form>
                <div className="story-room-chips">
                  {(demoAnswers ? demoAnswers[language].map((item) => item.question) : t.chips).map(
                    (chip) => (
                      <button
                        type="button"
                        disabled={busy}
                        key={chip}
                        onClick={() => void ask(chip)}
                      >
                        {chip}
                      </button>
                    ),
                  )}
                </div>
                {busy && (
                  <div className="story-room-working" role="status">
                    <span className="story-room-pulse" />
                    {t.busy}
                    <small>{pending ? '' : job?.message}</small>
                  </div>
                )}
                {(error || job?.error || loadError) && (
                  <p className="story-room-error" role="alert">
                    {error || job?.error || loadError}
                  </p>
                )}
                {!answer && !busy && (
                  <div className="story-room-empty">
                    <span aria-hidden="true">✧</span>
                    <h3>{t.empty}</h3>
                    <p>{t.emptyBody}</p>
                  </div>
                )}
                {answer && (
                  <article className="story-room-answer" aria-live="polite">
                    <p className="story-room-asked">“{answer.question}”</p>
                    <span
                      className={`story-room-confirmed ${answer.status === 'not_in_source' ? 'limited' : ''}`}
                    >
                      {demoAnswers
                        ? 'Prepared sample answer'
                        : answer.status === 'not_in_source'
                          ? t.missing
                          : t.confirmed}
                    </span>
                    <p className="story-room-answer-text">{answer.answer}</p>
                    {answer.caveat && (
                      <div className="story-room-caveat">
                        <strong>{t.caveat}</strong>
                        <p>{answer.caveat}</p>
                      </div>
                    )}
                    <div className="story-room-reply">
                      <div>
                        <strong>{t.reply}</strong>
                        <button type="button" onClick={() => void copyReply()}>
                          {copied ? '✓ ' + t.copied : t.copy}
                        </button>
                      </div>
                      <p>{answer.short_reply}</p>
                    </div>
                  </article>
                )}
                {answers.some((item) => item.language === language) && (
                  <nav className="story-room-history" aria-label={t.recent}>
                    <strong>{t.recent}</strong>
                    {answers
                      .filter((item) => item.language === language)
                      .slice(0, 4)
                      .map((item) => (
                        <button
                          type="button"
                          key={item.id}
                          disabled={busy}
                          onClick={() => {
                            setSelected(item)
                            setQuestion(item.question)
                            setPage(null)
                            setCopied(false)
                          }}
                        >
                          {item.question} <span aria-hidden="true">↗</span>
                        </button>
                      ))}
                  </nav>
                )}
              </section>
              <aside className="story-room-evidence">
                <div className="story-room-evidence-title">
                  <span aria-hidden="true">▤</span>
                  <h2>{t.source}</h2>
                </div>
                {answer ? (
                  answer.evidence.length ? (
                    answer.evidence.map((item, index) => (
                      <article key={index} className="story-room-citation">
                        <span>
                          {item.page !== null
                            ? `${t.page} ${item.page}`
                            : item.source_type === 'user'
                              ? 'User-provided source'
                              : item.url
                                ? 'Web source'
                                : 'Document excerpt'}
                        </span>
                        <blockquote>“{item.excerpt}”</blockquote>
                        {item.page !== null && (
                          <button
                            type="button"
                            onClick={() => setPage(page === index ? null : index)}
                          >
                            {page === index ? t.closePage : t.open}{' '}
                            <span aria-hidden="true">↗</span>
                          </button>
                        )}
                        {item.url && (
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            Open source ↗
                          </a>
                        )}
                      </article>
                    ))
                  ) : (
                    <p>{t.noEvidence}</p>
                  )
                ) : (
                  <div className="story-room-source-empty">
                    <span aria-hidden="true">⌕</span>
                    <p>{t.sourceEmpty}</p>
                    <small>
                      {demoAnswers
                        ? 'Prepared sample answer → fictional source excerpts'
                        : t.pipeline}
                    </small>
                  </div>
                )}
              </aside>
            </div>
            <footer className="story-room-footer">
              {demoAnswers
                ? 'Fictional sample · Prepared answers · No live AI generation'
                : t.draft}
            </footer>
          </main>
          {answer && page !== null && (
            <div
              className="story-room-page-overlay"
              role="dialog"
              aria-modal="true"
              aria-label="Original evidence page"
            >
              <div>
                <header>
                  <strong>
                    {t.source} · {t.page} {answer.evidence[page]?.page}
                  </strong>
                  <button type="button" onClick={() => setPage(null)}>
                    {t.closePage} ×
                  </button>
                </header>
                <img
                  src={`/api/story-room/${runId}/answers/${answer.id}/evidence/${page}`}
                  alt={`${t.source}, ${t.page} ${answer.evidence[page]?.page}`}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
