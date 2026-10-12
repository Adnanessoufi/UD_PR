import { useEffect, useRef, useState } from 'react'
import type { MediaAsset } from '../types/media'
import type { VideoStatus } from '../types/video'
import { videoBusy } from '../types/video'

export default function StudioMediaTray({
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
  const imageInput = useRef<HTMLInputElement>(null)
  const videoInput = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<MediaAsset | null>(null)
  const [showAdd, setShowAdd] = useState(false)

  useEffect(() => {
    if (expanded && !media.some((item) => item.id === expanded.id)) setExpanded(null)
  }, [expanded, media])

  useEffect(() => {
    if (!expanded) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(null)
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [expanded])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update media.')
    } finally {
      setBusy(false)
    }
  }

  function addImages(files: FileList | null) {
    const selected = files ? Array.from(files) : []
    if (imageInput.current) imageInput.current.value = ''
    if (selected.length) void run(() => onAddImages(selected))
  }

  function addVideo(files: FileList | null) {
    const selected = files?.[0]
    if (videoInput.current) videoInput.current.value = ''
    if (selected) void run(() => onAddVideo(selected))
  }

  return (
    <section className="studio-media-panel" id="studio-media" aria-label="Media assets">
      <div className="studio-section-top">
        <div>
          <h2>Media</h2>
          <p>All selected media appears in the package. The primary item appears first.</p>
        </div>
        <div className="studio-add-wrap">
          <button
            type="button"
            className="studio-outline-button"
            disabled={busy}
            onClick={() => setShowAdd((value) => !value)}
          >
            ＋ Add media
          </button>
          {showAdd && (
            <div className="studio-add-menu">
              {imageSelected && (
                <button
                  type="button"
                  onClick={() => {
                    imageInput.current?.click()
                    setShowAdd(false)
                  }}
                >
                  Add image
                </button>
              )}
              {videoSelected && (
                <button
                  type="button"
                  disabled={videoBusy(videoStatus?.stage)}
                  onClick={() => {
                    videoInput.current?.click()
                    setShowAdd(false)
                  }}
                >
                  Add video
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      <input
        ref={imageInput}
        type="file"
        accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
        multiple
        className="sr-only"
        aria-label="Add images"
        onChange={(event) => addImages(event.target.files)}
      />
      <input
        ref={videoInput}
        type="file"
        accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
        className="sr-only"
        aria-label="Add video"
        onChange={(event) => addVideo(event.target.files)}
      />
      <div className="studio-media-row" data-media-count={media.length}>
        {media.map((item) => (
          <div
            key={item.id}
            className={`studio-media-tile ${item.primary ? 'is-primary' : ''}`}
            data-media-asset={item.id}
          >
            <button
              type="button"
              className="studio-media-thumbnail"
              onClick={() => setExpanded(item)}
              aria-label={`Open ${item.label}`}
            >
              {item.media_type === 'video' ? (
                <>
                  <video src={item.url} preload="metadata" muted playsInline />
                  <span className="studio-play-mark">▶</span>
                </>
              ) : (
                <img src={item.url} alt="" />
              )}
              {item.primary && <span className="studio-primary-badge">✓ Primary</span>}
            </button>
            <div className="studio-media-tile-details">
              <span title={item.label}>{item.label}</span>
              <div>
                <button
                  type="button"
                  disabled={busy || item.primary}
                  onClick={() => void run(() => onChoosePrimary(item))}
                >
                  {item.primary ? 'Primary' : 'Make primary'}
                </button>
                <button
                  type="button"
                  disabled={
                    busy || (item.asset_type === 'uploaded_video' && videoBusy(videoStatus?.stage))
                  }
                  onClick={() =>
                    void run(() =>
                      onRemove(item, media.find((other) => other.id !== item.id)?.id || null),
                    )
                  }
                >
                  {item.asset_type === 'generated_video' ? 'Remove' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        ))}
        <button
          type="button"
          className="studio-media-add-tile"
          disabled={busy || (!imageSelected && !videoSelected)}
          onClick={() =>
            imageSelected ? imageInput.current?.click() : videoInput.current?.click()
          }
        >
          <span>＋</span>Add media
        </button>
      </div>
      {media.length === 0 && (
        <p className="studio-muted-note">No media assets are available yet.</p>
      )}
      {hideGeneratedVideo && videoStatus?.stage === 'ready' && (
        <button type="button" className="studio-link-button" onClick={onRestoreGeneratedVideo}>
          Add saved video back to post
        </button>
      )}
      {videoSelected && videoStatus?.stage === 'failed' && (
        <p className="studio-error" role="alert">
          {videoStatus.error}{' '}
          <button type="button" onClick={onRegenerateVideo}>
            Regenerate video
          </button>
        </p>
      )}
      {(assetError || error) && (
        <p className="studio-error" role="alert">
          {error || assetError}
        </p>
      )}
      {expanded && (
        <div className="studio-media-modal" role="presentation" onClick={() => setExpanded(null)}>
          <div
            className="studio-media-modal-content"
            role="dialog"
            aria-modal="true"
            aria-label={`${expanded.label} preview`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="studio-modal-top">
              <strong>{expanded.label}</strong>
              <button type="button" onClick={() => setExpanded(null)}>
                Close
              </button>
            </div>
            {expanded.media_type === 'video' ? (
              <video src={expanded.url} controls autoPlay playsInline />
            ) : (
              <img src={expanded.url} alt={expanded.label} />
            )}
            {expanded.asset_type === 'generated_video' && (
              <button type="button" className="studio-link-button" onClick={onRegenerateVideo}>
                Regenerate video
              </button>
            )}
            {expanded.media_type === 'image' && expanded.source === 'generated' && (
              <button
                type="button"
                className="studio-link-button"
                onClick={() => void run(onRetryImage)}
              >
                Regenerate image
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
