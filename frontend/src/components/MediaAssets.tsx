import { useEffect, useRef, useState } from 'react'
import type { MediaAsset } from '../types/media'
import type { VideoStatus } from '../types/video'
import { videoBusy } from '../types/video'

export default function MediaAssets({
  media,
  imageSelected,
  videoSelected,
  hideGeneratedVideo,
  videoStatus,
  assetError,
  onChoosePrimary,
  onRemove,
  onRestoreGeneratedVideo,
  onRetryImage,
  onRegenerateVideo,
  onAddImages,
  onAddVideo,
}: {
  media: MediaAsset[]
  imageSelected: boolean
  videoSelected: boolean
  hideGeneratedVideo: boolean
  videoStatus: VideoStatus | null
  assetError: string
  onChoosePrimary: (item: MediaAsset) => Promise<void>
  onRemove: (item: MediaAsset, nextPrimaryId: string | null) => Promise<void>
  onRestoreGeneratedVideo: () => void
  onRetryImage: () => Promise<void>
  onRegenerateVideo: () => void
  onAddImages: (files: File[]) => Promise<void>
  onAddVideo: (file: File) => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [expanded, setExpanded] = useState<MediaAsset | null>(null)
  const imageInput = useRef<HTMLInputElement>(null)
  const videoInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!expanded) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [expanded])

  useEffect(() => {
    if (expanded && !media.some((item) => item.id === expanded.id)) setExpanded(null)
  }, [media, expanded])

  async function act(action: () => Promise<void>) {
    setBusy(true)
    setActionError('')
    try {
      await action()
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Could not update media assets.')
    } finally {
      setBusy(false)
    }
  }

  function addImages(files: FileList | null) {
    const selected = files ? Array.from(files) : []
    if (imageInput.current) imageInput.current.value = ''
    if (selected.length) void act(() => onAddImages(selected))
  }

  function addVideo(files: FileList | null) {
    const selected = files?.[0]
    if (videoInput.current) videoInput.current.value = ''
    if (selected) void act(() => onAddVideo(selected))
  }

  return (
    <section className="mt-9 border-t border-[#edf1f6] pt-8" aria-label="Media assets">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-blue">Media assets</h3>
          <p className="mt-2 text-sm text-slate-500">
            Choose the primary media shown first in carousels and as the Website hero.
          </p>
        </div>
        <div className="flex gap-2">
          {imageSelected && (
            <>
              <input
                ref={imageInput}
                type="file"
                accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                multiple
                className="sr-only"
                aria-label="Add images"
                onChange={(event) => addImages(event.target.files)}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => imageInput.current?.click()}
                className="rounded-lg border border-[#d6e2f0] bg-white px-4 py-2 text-sm font-semibold text-blue disabled:opacity-50"
              >
                + Add image
              </button>
            </>
          )}
          {videoSelected && (
            <>
              <input
                ref={videoInput}
                type="file"
                accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
                className="sr-only"
                aria-label="Add video clip"
                onChange={(event) => addVideo(event.target.files)}
              />
              <button
                type="button"
                disabled={busy || videoBusy(videoStatus?.stage)}
                onClick={() => videoInput.current?.click()}
                className="rounded-lg border border-[#d6e2f0] bg-white px-4 py-2 text-sm font-semibold text-blue disabled:opacity-50"
              >
                + Add video clip
              </button>
            </>
          )}
        </div>
      </div>
      {media.length > 0 && (
        <div
          className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          data-media-count={media.length}
        >
          {media.map((item) => (
            <article
              key={item.id}
              data-media-asset={item.id}
              className={`overflow-hidden rounded-xl border bg-white ${item.primary ? 'border-blue shadow-[0_4px_18px_rgba(24,75,155,0.12)]' : 'border-[#dce5f0]'}`}
            >
              {item.media_type === 'image' ? (
                <button
                  type="button"
                  onClick={() => setExpanded(item)}
                  aria-label={`View ${item.label} larger`}
                  className="block w-full bg-[#f8fbff] focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
                >
                  <img src={item.url} alt={item.label} className="h-44 w-full object-contain" />
                </button>
              ) : (
                <video
                  src={item.url}
                  controls
                  preload="metadata"
                  playsInline
                  aria-label={item.label}
                  className="h-44 w-full bg-black object-contain"
                />
              )}
              <div className="space-y-2 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold">{item.label}</h4>
                  {item.recommended && (
                    <span className="rounded-full bg-pale-blue px-2 py-0.5 text-[10px] font-bold text-blue">
                      Recommended
                    </span>
                  )}
                </div>
                {item.source === 'document' && (
                  <p className="text-xs text-slate-500">From source document</p>
                )}
                {item.source === 'user' && (
                  <p className="text-xs text-slate-500">Uploaded by user</p>
                )}
                {item.asset_type === 'source_visual' && (
                  <p className="text-xs text-slate-500">Verify reuse rights before publication</p>
                )}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
                  <button
                    type="button"
                    disabled={busy || item.primary}
                    onClick={() => void act(() => onChoosePrimary(item))}
                    className="text-xs font-semibold text-blue disabled:text-slate-400"
                  >
                    {item.primary ? 'Primary media' : 'Make primary'}
                  </button>
                  {item.asset_type === 'generated_video' && (
                    <button
                      type="button"
                      disabled={busy || videoBusy(videoStatus?.stage)}
                      onClick={onRegenerateVideo}
                      className="text-xs font-semibold text-blue disabled:opacity-50"
                    >
                      Regenerate video
                    </button>
                  )}
                  {item.media_type === 'image' && item.source === 'generated' && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void act(onRetryImage)}
                      className="text-xs font-semibold text-blue disabled:opacity-50"
                    >
                      Regenerate
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={
                      busy ||
                      (item.asset_type === 'uploaded_video' && videoBusy(videoStatus?.stage))
                    }
                    onClick={() =>
                      void act(() =>
                        onRemove(item, media.find((other) => other.id !== item.id)?.id || null),
                      )
                    }
                    className="text-xs font-semibold text-slate-500 hover:text-red-600 disabled:opacity-50"
                  >
                    {item.asset_type === 'generated_video' ? 'Remove from post' : 'Delete'}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {media.length === 0 && (
        <p className="mt-5 rounded-xl border border-dashed border-[#cfdbeb] bg-[#f8fbff] px-4 py-5 text-sm text-slate-500">
          No media assets are available yet. Add an image or video clip to use in the previews.
        </p>
      )}
      {hideGeneratedVideo && videoStatus?.stage === 'ready' && (
        <button
          type="button"
          onClick={onRestoreGeneratedVideo}
          className="mt-4 text-sm font-semibold text-blue"
        >
          Add saved video back to post
        </button>
      )}
      {videoSelected && videoBusy(videoStatus?.stage) && (
        <p role="status" className="mt-4 text-sm text-slate-600">
          Preparing the generated video
          {videoStatus?.clips_total
            ? ` · ${videoStatus.clips_done || 0} / ${videoStatus.clips_total} clips`
            : '...'}
        </p>
      )}
      {videoSelected && videoStatus?.stage === 'failed' && (
        <div
          role="alert"
          className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {videoStatus.error}
          <button
            type="button"
            onClick={onRegenerateVideo}
            className="ml-3 font-semibold text-blue"
          >
            Regenerate video
          </button>
        </div>
      )}
      {(assetError || actionError) && (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          {actionError || assetError}
        </p>
      )}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 sm:p-8"
          role="presentation"
          onClick={() => setExpanded(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`${expanded.label} large preview`}
            onClick={(event) => event.stopPropagation()}
            className="flex max-h-[94vh] max-w-[94vw] flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
          >
            <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-4 py-3">
              <p className="text-sm font-semibold text-ink">{expanded.label}</p>
              <button
                type="button"
                onClick={() => setExpanded(null)}
                className="rounded-lg px-3 py-1.5 text-sm font-semibold text-blue hover:bg-pale-blue"
              >
                Close
              </button>
            </div>
            <div className="min-h-0 overflow-auto bg-[#f5f7fa] p-2 sm:p-4">
              <img
                src={expanded.url}
                alt={expanded.label}
                className="mx-auto block max-h-[78vh] max-w-full object-contain"
              />
            </div>
            {expanded.source === 'document' && (
              <p className="border-t border-slate-200 px-4 py-2 text-xs text-slate-500">
                From source document
              </p>
            )}
            {expanded.source === 'user' && (
              <p className="border-t border-slate-200 px-4 py-2 text-xs text-slate-500">
                Uploaded by user
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
