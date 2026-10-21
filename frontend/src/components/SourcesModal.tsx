import type { SourceAnalysis } from '../types/content'

export default function SourcesModal({
  analysis,
  sample = false,
  onClose,
}: {
  analysis: SourceAnalysis
  sample?: boolean
  onClose: () => void
}) {
  const quick = analysis.document_type === 'quick_announcement'
  const news = analysis.document_type === 'news_article'
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#11213b]/45 px-4 py-6"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="sources-heading"
        className="flex max-h-full w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-[0_20px_70px_rgba(12,30,60,0.2)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#e8edf4] p-6">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.17em] text-blue">
              Original sources
            </p>
            <h2 id="sources-heading" className="mt-2 text-xl font-semibold">
              Key facts & sources
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Here's where the facts in your draft came from.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close sources"
            className="rounded-lg px-2 py-1 text-xl text-slate-400 hover:bg-[#f2f6fb] hover:text-ink"
          >
            ×
          </button>
        </div>
        <div className="space-y-4 overflow-y-auto p-6">
          {analysis.warning && (
            <p
              role="status"
              className="rounded-md border border-[#ead8a7] bg-[#fffaf0] p-3 text-sm text-[#6b5119]"
            >
              {analysis.warning}
            </p>
          )}
          {analysis.key_facts.map((fact) => (
            <article key={fact.id} className="rounded-xl border border-[#e4ebf3] p-4">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-pale-blue px-2 py-1 text-xs font-bold text-blue">
                  {fact.id}
                </span>
                <span className="text-xs text-slate-500">
                  {sample
                    ? 'Fictional sample source'
                    : quick
                      ? fact.category === 'web_context'
                        ? 'Web source'
                        : fact.category === 'web_verified_announcement'
                          ? 'Web verified announcement'
                          : 'User announcement'
                      : fact.page === null
                        ? news
                          ? 'Collected article'
                          : 'DOCX source'
                        : `Page ${fact.page}`}
                </span>
              </div>
              <p className="mt-3 text-sm font-medium leading-6">{fact.statement}</p>
              <p className="mt-3 border-l-2 border-[#cbdcf1] pl-3 text-sm italic leading-6 text-slate-500">
                “{fact.source_excerpt}”
              </p>
            </article>
          ))}
          {analysis.research_sources && analysis.research_sources.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Research sources</h3>
              <ul className="space-y-3">
                {analysis.research_sources.map((source) => (
                  <li key={source.url}>
                    <a
                      className="text-sm font-semibold text-[#124a39] underline"
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {source.title}
                    </a>
                    <p className="text-xs text-slate-500">
                      {source.domain} ·{' '}
                      {source.source_type === 'official' ? 'Official source' : 'Secondary source'}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!analysis.research_sources?.length &&
            analysis.source_links &&
            analysis.source_links.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold">Research sources</h3>
                <ul className="space-y-2">
                  {analysis.source_links.map((link) => (
                    <li key={link}>
                      <a
                        className="break-all text-sm text-[#124a39] underline"
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
        </div>
      </section>
    </div>
  )
}
