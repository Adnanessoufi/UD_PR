import SelectionShell from '../components/SelectionShell'
import VideoMedia from '../components/VideoMedia'
import type { ProcessingState } from '../components/ProcessingStatus'
import {
  platformAvailability,
  platformLabels,
  platformOrder,
  type ContentType,
  type PlatformName,
} from '../types/platform'
import type { UploadResult } from '../types/upload'
import type { UploadedVideo } from '../types/video'

const marks: Record<PlatformName, string> = {
  website: 'UD',
  linkedin: 'in',
  facebook: 'f',
  instagram: '◎',
  tiktok: '♪',
  youtube: '▶',
}

export default function PlatformPage({
  document,
  contentTypes,
  selected,
  processing,
  processingError,
  videoUploads,
  videoBusy,
  onAddVideo,
  onDeleteVideo,
  onToggle,
  onBack,
  onGenerate,
  onRetry,
  onNewDocument,
}: {
  document: UploadResult
  contentTypes: ContentType[]
  selected: PlatformName[]
  processing: ProcessingState
  processingError: string
  videoUploads: UploadedVideo[]
  videoBusy: boolean
  onAddVideo: (file: File) => Promise<void>
  onDeleteVideo: (id: string) => Promise<void>
  onToggle: (platform: PlatformName) => void
  onBack: () => void
  onGenerate: () => void
  onRetry: () => void
  onNewDocument: () => void
}) {
  return (
    <SelectionShell
      step="Step 03 · Platforms"
      title="Where would you like to publish?"
      subtitle="Choose one or more destinations for your communication."
      document={document}
      processing={processing}
      processingError={processingError}
      onRetry={onRetry}
      onNewDocument={onNewDocument}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {platformOrder.map((platform) => {
          const { enabled, reason } = platformAvailability(platform, contentTypes)
          const active = selected.includes(platform)
          return (
            <button
              key={platform}
              type="button"
              disabled={!enabled}
              aria-pressed={active}
              onClick={() => onToggle(platform)}
              className={`min-h-40 rounded-[20px] border-2 p-5 text-left transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue ${!enabled ? 'cursor-not-allowed border-[#e8edf3] bg-[#f8fafc] opacity-65' : active ? 'border-blue bg-[#f5f9fe] shadow-[0_8px_26px_rgba(24,75,155,0.08)]' : 'border-[#e2eaf3] bg-white hover:border-[#a9bfdc]'}`}
            >
              <div className="flex items-start justify-between">
                <span
                  className={`flex h-11 w-11 items-center justify-center rounded-xl text-sm font-bold ${active ? 'bg-blue text-white' : 'bg-pale-blue text-blue'}`}
                >
                  {marks[platform]}
                </span>
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-bold ${active ? 'border-blue bg-blue text-white' : 'border-[#cbd8e8] text-transparent'}`}
                >
                  ✓
                </span>
              </div>
              <h2 className="mt-5 text-base font-semibold">{platformLabels[platform]}</h2>
              {!enabled && <p className="mt-1 text-xs text-slate-500">{reason}</p>}
            </button>
          )
        })}
      </div>
      {contentTypes.includes('video') && (
        <VideoMedia
          uploads={videoUploads}
          busy={videoBusy}
          onAdd={onAddVideo}
          onDelete={onDeleteVideo}
        />
      )}
      <div className="mt-8 flex items-center justify-between gap-4">
        <button onClick={onBack} className="text-sm font-semibold text-slate-500 hover:text-blue">
          ← Back
        </button>
        <button
          onClick={onGenerate}
          disabled={selected.length === 0}
          className="inline-flex min-w-40 items-center justify-center gap-2 rounded-xl bg-blue px-6 py-4 text-sm font-semibold text-white shadow-[0_9px_20px_rgba(24,75,155,0.18)] hover:bg-[#123e85] disabled:cursor-not-allowed disabled:bg-[#aabbd1] disabled:shadow-none"
        >
          Generate <span aria-hidden="true">→</span>
        </button>
      </div>
    </SelectionShell>
  )
}
