import type { VideoStatus } from '../types/video'

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
