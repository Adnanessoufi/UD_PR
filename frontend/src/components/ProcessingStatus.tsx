export type ProcessingState = 'processing' | 'ready' | 'failed'

export default function ProcessingStatus({
  status,
  error,
  onRetry,
}: {
  status: ProcessingState
  error: string
  onRetry: () => void
}) {
  if (status === 'ready') {
    return (
      <div
        className="inline-flex items-center gap-2 rounded-full bg-[#f1faf5] px-3 py-2 text-xs font-medium text-[#248261]"
        role="status"
      >
        <span className="text-sm">✓</span> Document understood
      </div>
    )
  }
  if (status === 'failed') {
    return (
      <div
        className="flex flex-wrap items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
        role="alert"
      >
        <span>{error || 'Document analysis failed.'}</span>
        <button onClick={onRetry} className="font-bold underline underline-offset-2">
          Retry analysis
        </button>
      </div>
    )
  }
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full bg-[#f3f7fc] px-3 py-2 text-xs font-medium text-blue"
      role="status"
    >
      <span className="h-2 w-2 animate-pulse rounded-full bg-blue" /> AI is reading your document...
    </div>
  )
}
