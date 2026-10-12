import SelectionShell from '../components/SelectionShell'
import type { ProcessingState } from '../components/ProcessingStatus'
import type { ContentType } from '../types/platform'
import type { UploadResult } from '../types/upload'

const options: { id: ContentType; label: string; description: string }[] = [
  { id: 'text', label: 'Text', description: 'Press releases, articles and social posts' },
  { id: 'image', label: 'Image', description: 'Visual communication content' },
  { id: 'video', label: 'Video', description: 'Short communication video' },
]

function FormatIcon({ format }: { format: ContentType }) {
  if (format === 'text')
    return (
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
        <path d="M5 3.5h10l4 4V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
        <path d="M15 3.5V8h4M8 12h8M8 16h6" />
      </svg>
    )
  if (format === 'image')
    return (
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
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <circle cx="8" cy="9" r="1.5" />
        <path d="m4 17 5-5 3 3 3-3 5 5" />
      </svg>
    )
  return (
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
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m10 9 5 3-5 3V9Z" />
    </svg>
  )
}

export default function FormatPage({
  document,
  selected,
  processing,
  processingError,
  onToggle,
  onContinue,
  onRetry,
  onNewDocument,
}: {
  document: UploadResult
  selected: ContentType[]
  processing: ProcessingState
  processingError: string
  onToggle: (format: ContentType) => void
  onContinue: () => void
  onRetry: () => void
  onNewDocument: () => void
}) {
  return (
    <SelectionShell
      step="Step 02 · Formats"
      title="What would you like to create?"
      subtitle="Choose one or more communication formats."
      document={document}
      processing={processing}
      processingError={processingError}
      onRetry={onRetry}
      onNewDocument={onNewDocument}
    >
      <div className="grid gap-4 md:grid-cols-3">
        {options.map((option) => {
          const active = selected.includes(option.id)
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={active}
              onClick={() => onToggle(option.id)}
              className={`min-h-64 rounded-[22px] border-2 p-6 text-left transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue ${active ? 'border-blue bg-[#f5f9fe] shadow-[0_10px_30px_rgba(24,75,155,0.09)]' : 'border-[#e2eaf3] bg-white hover:border-[#a9bfdc] hover:shadow-[0_8px_24px_rgba(25,54,96,0.06)]'}`}
            >
              <div className="flex items-start justify-between">
                <span
                  className={`flex h-14 w-14 items-center justify-center rounded-2xl ${active ? 'bg-white text-blue' : 'bg-pale-blue text-blue'}`}
                >
                  <FormatIcon format={option.id} />
                </span>
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-bold ${active ? 'border-blue bg-blue text-white' : 'border-[#cbd8e8] text-transparent'}`}
                >
                  ✓
                </span>
              </div>
              <h2 className="mt-8 text-lg font-semibold">{option.label}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">{option.description}</p>
            </button>
          )
        })}
      </div>
      <div className="mt-8 flex justify-end">
        <button
          onClick={onContinue}
          disabled={selected.length === 0}
          className="inline-flex min-w-40 items-center justify-center gap-2 rounded-xl bg-blue px-6 py-4 text-sm font-semibold text-white shadow-[0_9px_20px_rgba(24,75,155,0.18)] hover:bg-[#123e85] disabled:cursor-not-allowed disabled:bg-[#aabbd1] disabled:shadow-none"
        >
          Continue <span aria-hidden="true">→</span>
        </button>
      </div>
    </SelectionShell>
  )
}
