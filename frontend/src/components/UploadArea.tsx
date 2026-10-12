import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'

type Props = {
  file: File | null
  disabled: boolean
  onSelect: (file: File) => void
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadArea({ file, disabled, onSelect }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0]
    if (selected) onSelect(selected)
    event.target.value = ''
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (!disabled && event.dataTransfer.files[0]) onSelect(event.dataTransfer.files[0])
  }

  return (
    <div
      className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 ${
        dragging
          ? 'border-blue bg-blue/5 shadow-[0_0_0_4px_rgba(24,75,155,0.08)]'
          : 'border-[#cbd8e8] bg-[#f8fbff] hover:border-[#9db9dc] hover:bg-[#f3f8fe]'
      } ${disabled ? 'opacity-60' : ''}`}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false)
      }}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleInput}
        disabled={disabled}
        aria-label="Choose a PDF or DOCX document"
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="flex w-full flex-col items-center px-6 py-10 text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue sm:py-12"
      >
        <span className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-blue shadow-[0_7px_22px_rgba(19,62,117,0.09)] ring-1 ring-[#e5edf7]">
          {file ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-8 w-8"
              aria-hidden="true"
            >
              <path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
              <path d="M14 3.5V8h4M9 12h6M9 16h6" />
            </svg>
          ) : (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-8 w-8"
              aria-hidden="true"
            >
              <path d="M12 16V4m0 0L8 8m4-4 4 4" />
              <path d="M4 16.5v2A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5v-2" />
            </svg>
          )}
        </span>
        {file ? (
          <>
            <span className="max-w-full truncate text-base font-semibold text-ink">
              {file.name}
            </span>
            <span className="mt-1 text-sm text-slate-500">
              {file.name.split('.').pop()?.toUpperCase()} · {formatSize(file.size)}
            </span>
            <span className="mt-5 text-sm font-semibold text-blue">Choose a different file</span>
          </>
        ) : (
          <>
            <span className="text-base font-semibold text-ink">
              Drag and drop your document here
            </span>
            <span className="mt-2 text-sm text-slate-500">
              or{' '}
              <span className="font-semibold text-blue underline underline-offset-2">
                browse files
              </span>{' '}
              from your device
            </span>
            <span className="mt-6 rounded-full border border-[#dbe6f2] bg-white px-3 py-1 text-xs font-medium text-slate-500">
              PDF or DOCX
            </span>
          </>
        )}
      </button>
    </div>
  )
}
