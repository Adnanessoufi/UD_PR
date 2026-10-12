import type { ReactNode } from 'react'
import ProcessingStatus, { type ProcessingState } from './ProcessingStatus'
import type { UploadResult } from '../types/upload'

export default function SelectionShell({
  step,
  title,
  subtitle,
  document,
  processing,
  processingError,
  onRetry,
  onNewDocument,
  children,
}: {
  step: string
  title: string
  subtitle: string
  document: UploadResult
  processing: ProcessingState
  processingError: string
  onRetry: () => void
  onNewDocument: () => void
  children: ReactNode
}) {
  return (
    <div className="min-h-screen bg-white text-ink">
      <div className="h-1 w-full bg-blue" />
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue text-[13px] font-bold tracking-[-0.08em] text-white shadow-[0_7px_16px_rgba(24,75,155,0.16)]">
            UD
          </span>
          <span className="text-[15px] font-bold tracking-tight">PR Studio</span>
        </div>
        <button
          onClick={onNewDocument}
          className="text-sm font-medium text-slate-500 hover:text-blue"
        >
          New document
        </button>
      </header>
      <main className="mx-auto max-w-5xl px-6 pb-20 pt-10 sm:px-8 sm:pt-16">
        <div className="mb-10 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-2xl">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue">{step}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">{title}</h1>
            <p className="mt-3 text-sm leading-6 text-slate-500 sm:text-base">{subtitle}</p>
            <p className="mt-4 truncate text-xs text-slate-400">Source: {document.filename}</p>
            {document.cached && (
              <p className="mt-3 text-sm font-semibold text-green-700">Saved results found ✓</p>
            )}
          </div>
          <ProcessingStatus status={processing} error={processingError} onRetry={onRetry} />
        </div>
        {children}
      </main>
      <footer className="mx-auto flex max-w-6xl items-center justify-between border-t border-[#edf1f5] px-6 py-6 text-xs text-slate-400 sm:px-8">
        <span>UD PR Studio</span>
        <span>Communication workspace</span>
      </footer>
    </div>
  )
}
