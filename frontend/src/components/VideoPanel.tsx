import type { VideoStatus } from '../types/video'
import { videoBusy } from '../types/video'

const labels: Record<string, string> = {
  idle: 'Video has not started.',
  planning: 'Planning grounded scenes...',
  narration: 'Creating narration...',
  generating_clips: 'Generating motion clips...',
  composing: 'Building final video...',
  ready: 'Video is ready.',
  failed: 'Video generation stopped.',
}

export function VideoPlayer({
  status,
  className = '',
}: {
  status: VideoStatus | null
  className?: string
}) {
  if (status?.stage === 'ready' && status.url)
    return (
      <video
        src={status.url}
        controls
        preload="metadata"
        playsInline
        className={`aspect-video w-full bg-black object-contain ${className}`}
      />
    )
  return (
    <div
      className={`flex aspect-video items-center justify-center bg-[#102944] px-6 text-center text-sm text-white ${className}`}
      role="status"
    >
      {status?.stage === 'failed' ? status.error : labels[status?.stage || 'idle']}
    </div>
  )
}

export default function VideoPanel({
  status,
  onRegenerate,
}: {
  status: VideoStatus | null
  onRegenerate: () => void
}) {
  return (
    <section
      className="mt-8 rounded-xl border border-[#dce6f2] bg-white p-5"
      aria-label="Master video"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue">Video</p>
          <h3 className="mt-1 text-lg font-semibold">
            One master video for every selected platform
          </h3>
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={videoBusy(status?.stage)}
          className="rounded-lg border border-blue px-4 py-2 text-sm font-semibold text-blue disabled:opacity-50"
        >
          Regenerate video
        </button>
      </div>
      <VideoPlayer status={status} className="rounded-lg" />
      {videoBusy(status?.stage) && (
        <p className="mt-3 text-sm text-slate-600" role="status">
          {labels[status?.stage || 'idle']}
          {status?.stage === 'generating_clips' && status.clips_total
            ? ` ${status.clips_done || 0} / ${status.clips_total}`
            : ''}
        </p>
      )}
      {status?.stage === 'failed' && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {status.error}
        </p>
      )}
      {status?.stage === 'ready' && (
        <p className="mt-3 text-xs text-slate-500">
          {status.duration_seconds?.toFixed(1)} seconds ·{' '}
          {Math.round((status.motion_ratio || 0) * 100)}% moving footage · English narration and
          burned captions
        </p>
      )}
    </section>
  )
}
