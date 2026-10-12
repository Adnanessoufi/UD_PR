import { useEffect, useRef, useState } from 'react'
import { generateMaster, processDocument, saveMaster } from '../services/content'
import type { MasterContent, SourceAnalysis } from '../types/content'
import type { UploadResult } from '../types/upload'

type Tab = 'story' | 'press' | 'sources'
type Busy = 'analyzing' | 'regenerating' | 'saving' | null
type RetryAction = 'process' | 'regenerate' | 'save' | null

export default function ContentPage({
  document,
  onNewDocument,
}: {
  document: UploadResult
  onNewDocument: () => void
}) {
  const [analysis, setAnalysis] = useState<SourceAnalysis | null>(null)
  const [content, setContent] = useState<MasterContent | null>(null)
  const [tab, setTab] = useState<Tab>('story')
  const [busy, setBusy] = useState<Busy>('analyzing')
  const [error, setError] = useState('')
  const [retryAction, setRetryAction] = useState<RetryAction>(null)
  const [editing, setEditing] = useState<'story' | 'press' | null>(null)
  const [draft, setDraft] = useState<MasterContent | null>(null)
  const started = useRef(false)

  async function process() {
    setError('')
    setBusy('analyzing')
    try {
      const result = await processDocument(document.run_id)
      setAnalysis(result.analysis)
      setContent(result.content)
      setBusy(null)
      setRetryAction(null)
    } catch (cause) {
      setBusy(null)
      setRetryAction('process')
      setError(cause instanceof Error ? cause.message : 'Content generation failed. Please retry.')
    }
  }

  useEffect(() => {
    if (started.current) return
    started.current = true
    void process()
  }, [])

  async function regenerate() {
    setError('')
    setBusy('regenerating')
    try {
      const generated = await generateMaster(document.run_id)
      setContent(generated)
      setBusy(null)
      setRetryAction(null)
    } catch (cause) {
      setBusy(null)
      setRetryAction('regenerate')
      setError(cause instanceof Error ? cause.message : 'Regeneration failed. Please retry.')
    }
  }

  function beginEdit(section: 'story' | 'press') {
    if (!content) return
    setDraft({ ...content })
    setEditing(section)
    setError('')
  }

  function updateDraft(
    field: 'headline' | 'lead' | 'short_summary' | 'body' | 'press_release',
    value: string,
  ) {
    setDraft((current) => (current ? { ...current, [field]: value } : current))
  }

  async function saveEdit() {
    if (!draft) return
    setError('')
    setBusy('saving')
    try {
      const saved = await saveMaster(document.run_id, draft)
      setContent(saved)
      setEditing(null)
      setDraft(null)
      setBusy(null)
      setRetryAction(null)
    } catch (cause) {
      setBusy(null)
      setRetryAction('save')
      setError(cause instanceof Error ? cause.message : 'Could not save the content. Please retry.')
    }
  }

  function retry() {
    if (retryAction === 'process') void process()
    if (retryAction === 'regenerate') void regenerate()
    if (retryAction === 'save') void saveEdit()
  }

  const analyzing = busy === 'analyzing'
  const analysisDone = Boolean(analysis)
  const contentDone = Boolean(content)

  return (
    <div className="min-h-screen bg-[#fbfcfe] text-ink">
      <div className="h-1 w-full bg-blue" />
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue text-[13px] font-bold tracking-[-0.08em] text-white shadow-[0_7px_16px_rgba(24,75,155,0.16)]">
            UD
          </span>
          <span className="text-[15px] font-bold tracking-tight text-ink">PR Studio</span>
        </div>
        <button
          onClick={onNewDocument}
          className="text-sm font-medium text-slate-500 hover:text-blue"
        >
          New document
        </button>
      </header>

      <main className="mx-auto max-w-5xl px-6 pb-20 pt-8 sm:px-8 sm:pt-12">
        <div className="mb-8">
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-blue">
            Document workspace
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
            Master PR Content
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
            A single source-grounded story developed from{' '}
            <span className="font-medium text-ink">{document.filename}</span>. Review and edit the
            wording before using it.
          </p>
        </div>

        <section
          className="mb-7 rounded-2xl border border-[#e5ebf3] bg-white p-5 shadow-[0_8px_30px_rgba(25,54,96,0.04)] sm:p-6"
          aria-label="Processing progress"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <StepIcon done />
              <span className="text-sm font-medium text-ink">Reading source</span>
            </div>
            <span className="hidden h-px w-8 bg-[#dce5f0] sm:block" />
            <div className="flex items-center gap-3">
              <StepIcon done={analysisDone} active={analyzing} />
              <span
                className={`text-sm ${analysisDone || analyzing ? 'font-medium text-ink' : 'text-slate-400'}`}
              >
                Extracting key information
              </span>
            </div>
            <span className="hidden h-px w-8 bg-[#dce5f0] sm:block" />
            <div className="flex items-center gap-3">
              <StepIcon done={contentDone} />
              <span
                className={`text-sm ${contentDone ? 'font-medium text-ink' : 'text-slate-400'}`}
              >
                Creating communication content
              </span>
            </div>
          </div>
          {analyzing && (
            <p className="mt-5 border-t border-[#edf1f6] pt-4 text-sm text-slate-500" role="status">
              Extracting key information and creating communication content...
            </p>
          )}
        </section>

        {error && (
          <div
            className="mb-7 flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between"
            role="alert"
          >
            <span>{error}</span>
            <button
              onClick={retry}
              disabled={busy !== null}
              className="shrink-0 rounded-lg border border-red-200 bg-white px-4 py-2 font-semibold text-red-700 hover:bg-red-50 disabled:opacity-60"
            >
              Retry
            </button>
          </div>
        )}

        {!content ? (
          <div className="rounded-2xl border border-[#e5ebf3] bg-white px-6 py-16 text-center shadow-[0_8px_30px_rgba(25,54,96,0.04)]">
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-pale-blue text-blue">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-7 w-7"
                aria-hidden="true"
              >
                <path d="M6 3h9l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
                <path d="M15 3v5h4M8 12h8M8 16h6" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold">
              {error ? 'Processing paused' : 'Preparing your content'}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {error
                ? 'Resolve the issue above and retry this step.'
                : 'This may take a little while for a longer document.'}
            </p>
          </div>
        ) : (
          <section className="overflow-hidden rounded-2xl border border-[#e5ebf3] bg-white shadow-[0_8px_30px_rgba(25,54,96,0.05)]">
            <div
              className="flex overflow-x-auto border-b border-[#e8edf4] px-4 sm:px-7"
              role="tablist"
              aria-label="Master content sections"
            >
              {(
                [
                  ['story', 'Master Story'],
                  ['press', 'Press Release'],
                  ['sources', 'Sources'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                  className={`shrink-0 border-b-2 px-4 py-5 text-sm font-semibold transition-colors sm:px-5 ${tab === id ? 'border-blue text-blue' : 'border-transparent text-slate-500 hover:text-ink'}`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="p-6 sm:p-9">
              {tab !== 'sources' && (
                <div className="mb-7 flex flex-wrap items-center justify-between gap-3 border-b border-[#edf1f6] pb-6">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue">
                      {tab === 'story' ? 'Master story' : 'Formal press release'}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {tab === 'story'
                        ? 'The central version of this story.'
                        : 'A ready-to-review press release draft.'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => (editing === tab ? void saveEdit() : beginEdit(tab))}
                      disabled={busy !== null || (editing !== null && editing !== tab)}
                      className="rounded-lg border border-[#d6e2f0] px-4 py-2 text-sm font-semibold text-blue hover:bg-[#f4f8fd] disabled:opacity-50"
                    >
                      {editing === tab ? (busy === 'saving' ? 'Saving...' : 'Save') : 'Edit'}
                    </button>
                    <button
                      onClick={() => void regenerate()}
                      disabled={busy !== null || editing !== null}
                      className="rounded-lg border border-[#d6e2f0] px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-[#f4f8fd] disabled:opacity-50"
                    >
                      {busy === 'regenerating' ? 'Regenerating...' : 'Regenerate'}
                    </button>
                  </div>
                </div>
              )}

              {busy === 'regenerating' && (
                <p
                  className="mb-6 rounded-lg bg-pale-blue px-4 py-3 text-sm text-blue"
                  role="status"
                >
                  Creating a new master story from the saved facts...
                </p>
              )}

              {tab === 'story' && (
                <div className="space-y-7">
                  <div>
                    <FieldLabel>Headline</FieldLabel>
                    {editing === 'story' ? (
                      <input
                        value={draft?.headline || ''}
                        onChange={(event) => updateDraft('headline', event.target.value)}
                        className="mt-2 w-full rounded-lg border border-[#cbd8e8] px-4 py-3 text-xl font-semibold outline-none focus:border-blue"
                      />
                    ) : (
                      <h2 className="mt-2 text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
                        {content.headline}
                      </h2>
                    )}
                  </div>
                  <div>
                    <FieldLabel>Lead</FieldLabel>
                    {editing === 'story' ? (
                      <textarea
                        rows={3}
                        value={draft?.lead || ''}
                        onChange={(event) => updateDraft('lead', event.target.value)}
                        className="mt-2 w-full rounded-lg border border-[#cbd8e8] px-4 py-3 text-sm leading-7 outline-none focus:border-blue"
                      />
                    ) : (
                      <p className="mt-2 text-base leading-8 text-slate-700">{content.lead}</p>
                    )}
                  </div>
                  <div>
                    <FieldLabel>Short summary</FieldLabel>
                    {editing === 'story' ? (
                      <textarea
                        rows={3}
                        value={draft?.short_summary || ''}
                        onChange={(event) => updateDraft('short_summary', event.target.value)}
                        className="mt-2 w-full rounded-lg border border-[#cbd8e8] px-4 py-3 text-sm leading-7 outline-none focus:border-blue"
                      />
                    ) : (
                      <p className="mt-2 text-sm leading-7 text-slate-600">
                        {content.short_summary}
                      </p>
                    )}
                  </div>
                  <div>
                    <FieldLabel>Main story</FieldLabel>
                    {editing === 'story' ? (
                      <textarea
                        rows={14}
                        value={draft?.body || ''}
                        onChange={(event) => updateDraft('body', event.target.value)}
                        className="mt-2 w-full rounded-lg border border-[#cbd8e8] px-4 py-3 text-sm leading-7 outline-none focus:border-blue"
                      />
                    ) : (
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-8 text-slate-700">
                        {content.body}
                      </p>
                    )}
                  </div>
                  {content.key_messages.length > 0 && (
                    <div className="rounded-xl bg-[#f6f9fd] p-5">
                      <FieldLabel>Key messages</FieldLabel>
                      <ul className="mt-3 space-y-2">
                        {content.key_messages.map((message, index) => (
                          <li key={index} className="flex gap-2 text-sm leading-6 text-slate-700">
                            <span className="text-blue">•</span>
                            {message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {tab === 'press' && (
                <div>
                  {editing === 'press' ? (
                    <textarea
                      rows={24}
                      value={draft?.press_release || ''}
                      onChange={(event) => updateDraft('press_release', event.target.value)}
                      className="w-full rounded-lg border border-[#cbd8e8] px-4 py-3 text-sm leading-8 outline-none focus:border-blue"
                      aria-label="Press release"
                    />
                  ) : (
                    <article className="whitespace-pre-wrap text-sm leading-8 text-slate-700">
                      {content.press_release}
                    </article>
                  )}
                </div>
              )}

              {tab === 'sources' && analysis && (
                <div>
                  <div className="mb-7">
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue">
                      Key facts & sources
                    </p>
                    <h2 className="mt-2 text-xl font-semibold">Evidence behind the story</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{analysis.summary}</p>
                  </div>
                  <div className="space-y-4">
                    {analysis.key_facts.map((fact) => (
                      <div key={fact.id} className="rounded-xl border border-[#e4ebf3] p-5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md bg-pale-blue px-2.5 py-1 text-xs font-bold text-blue">
                            {fact.id}
                          </span>
                          <span className="text-xs text-slate-500">
                            {fact.page === null ? 'DOCX source' : `Page ${fact.page}`}
                          </span>
                          <span className="text-xs text-slate-400">
                            · {fact.category.replace(/_/g, ' ')}
                          </span>
                        </div>
                        <p className="mt-3 text-sm font-medium leading-6 text-ink">
                          {fact.statement}
                        </p>
                        <p className="mt-3 border-l-2 border-[#cbdcf1] pl-3 text-sm italic leading-6 text-slate-500">
                          “{fact.source_excerpt}”
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}
      </main>
      <footer className="mx-auto flex max-w-6xl items-center justify-between border-t border-[#edf1f5] px-6 py-6 text-xs text-slate-400 sm:px-8">
        <span>UD PR Studio</span>
        <span>Master content review</span>
      </footer>
    </div>
  )
}

function StepIcon({ done = false, active = false }: { done?: boolean; active?: boolean }) {
  return (
    <span
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${done ? 'bg-[#def3e8] text-[#248261]' : active ? 'bg-pale-blue text-blue' : 'bg-[#f0f3f7] text-slate-400'}`}
    >
      {done ? (
        '✓'
      ) : active ? (
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-blue" />
      ) : (
        '·'
      )}
    </span>
  )
}

function FieldLabel({ children }: { children: string }) {
  return (
    <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-slate-500">{children}</h3>
  )
}
