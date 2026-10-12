import { useState } from 'react'
import UploadArea from '../components/UploadArea'
import YouTubeConnection from '../components/YouTubeConnection'
import { uploadDocument } from '../services/upload'
import type { UploadResult } from '../types/upload'

type Stage = 'select' | 'uploading'

export default function UploadPage({
  onUploaded,
}: {
  onUploaded: (document: UploadResult) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [stage, setStage] = useState<Stage>('select')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')

  function selectFile(selected: File) {
    setError('')
    setProgress(0)
    setStage('select')
    if (!/\.(pdf|docx)$/i.test(selected.name)) {
      setFile(null)
      setError('Unsupported file type. Please choose a PDF or DOCX file.')
      return
    }
    if (selected.size === 0) {
      setFile(null)
      setError('The selected file is empty. Please choose another document.')
      return
    }
    setFile(selected)
  }

  async function processDocument() {
    if (!file) return
    setError('')
    setStage('uploading')
    try {
      const uploaded = await uploadDocument(file, setProgress)
      onUploaded(uploaded)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The document could not be processed.')
      setStage('select')
    }
  }

  return (
    <div className="min-h-screen bg-white text-ink">
      <div className="h-1 w-full bg-blue" />
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue text-[13px] font-bold tracking-[-0.08em] text-white shadow-[0_7px_16px_rgba(24,75,155,0.16)]">
            UD
          </span>
          <span className="text-[15px] font-bold tracking-tight text-ink">PR Studio</span>
        </div>
        <span className="hidden items-center gap-2 text-xs font-medium tracking-wide text-slate-500 sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-[#43aa8b]" /> DOCUMENT WORKSPACE
        </span>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20 pt-12 sm:px-8 sm:pt-20">
        <div className="mx-auto max-w-[760px] text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-[#dbe7f5] bg-[#f5f9fe] px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.17em] text-blue">
            <span className="h-1.5 w-1.5 rounded-full bg-blue" /> From source to story
          </span>
          <h1 className="mt-7 text-[clamp(2.55rem,5vw,4.25rem)] font-semibold leading-[1.08] tracking-[-0.065em] text-ink">
            Turn documents into <span className="text-blue">communication.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-[600px] text-[15px] leading-7 text-slate-500 sm:text-base">
            Upload scientific, educational, technical or institutional material and transform it
            into ready-to-use PR content.
          </p>
        </div>

        <section
          className="mx-auto mt-12 max-w-[650px] rounded-[26px] border border-[#e5ebf3] bg-white p-5 shadow-[0_18px_65px_rgba(25,54,96,0.09)] sm:p-8"
          aria-labelledby="upload-heading"
        >
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue">
                Step 01 · Source material
              </p>
              <h2
                id="upload-heading"
                className="mt-2 text-xl font-semibold tracking-tight text-ink"
              >
                Upload a document
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Start with the material you want to communicate.
              </p>
            </div>
            <span className="hidden rounded-full border border-[#e1eaf4] px-3 py-1 text-xs font-medium text-slate-500 sm:block">
              PDF / DOCX
            </span>
          </div>

          <UploadArea file={file} disabled={stage === 'uploading'} onSelect={selectFile} />

          {error && (
            <p
              className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              role="alert"
            >
              {error}
            </p>
          )}

          {stage === 'uploading' && (
            <div className="mt-5" role="status" aria-live="polite">
              <div className="flex justify-between text-sm">
                <span className="font-medium text-ink">Reading your document...</span>
                <span className="text-slate-500">
                  {progress < 100 ? `${progress}% uploaded` : 'Processing'}
                </span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#e8eff8]">
                <div
                  className={`h-full rounded-full bg-blue transition-all duration-300 ${progress === 100 ? 'animate-pulse' : ''}`}
                  style={{ width: `${Math.max(progress, 5)}%` }}
                />
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={processDocument}
            disabled={!file || stage === 'uploading'}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-blue px-5 py-4 text-sm font-semibold text-white shadow-[0_9px_20px_rgba(24,75,155,0.18)] transition-colors hover:bg-[#123e85] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue disabled:cursor-not-allowed disabled:bg-[#aabbd1] disabled:shadow-none"
          >
            Continue
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              aria-hidden="true"
            >
              <path d="M5 12h14m-6-6 6 6-6 6" />
            </svg>
          </button>
        </section>

        <YouTubeConnection />

        <div className="mx-auto mt-9 flex max-w-[650px] items-start gap-3 px-2 text-xs leading-5 text-slate-400">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mt-0.5 h-4 w-4 shrink-0 text-slate-400"
            aria-hidden="true"
          >
            <rect x="4" y="10" width="16" height="11" rx="2" />
            <path d="M8 10V7a4 4 0 0 1 8 0v3" />
          </svg>
          <span>
            Your file is stored locally on the server. PDF text is captured page by page; DOCX
            paragraphs are captured in order.
          </span>
        </div>
      </main>
      <footer className="mx-auto flex max-w-6xl items-center justify-between border-t border-[#edf1f5] px-6 py-6 text-xs text-slate-400 sm:px-8">
        <span>UD PR Studio</span>
        <span>Document intake</span>
      </footer>
    </div>
  )
}
