import { useRef, useState } from 'react'
import SourcesModal from '../components/SourcesModal'
import PlatformMockup from '../components/PlatformMockup'
import MediaAssets from '../components/MediaAssets'
import YouTubePublisher from '../components/YouTubePublisher'
import TikTokPublisher from '../components/TikTokPublisher'
import MetaPublisher from '../components/MetaPublisher'
import UniversityPublisher from '../components/UniversityPublisher'
import type { AssetPack } from '../types/assets'
import type { PackageProgress, StageState } from '../types/generation'
import { orderedMediaAssets, type MediaAsset } from '../types/media'
import type { MasterContent, SourceAnalysis } from '../types/content'
import {
  platformLabels,
  type ContentType,
  type PlatformName,
  type PlatformResult,
} from '../types/platform'
import type { UploadResult } from '../types/upload'
import type { UploadedVideo, VideoStatus } from '../types/video'

type PreviewState = 'waiting' | 'ready' | 'error'

function StageLine({
  state,
  pending,
  ready,
  failed,
}: {
  state: StageState
  pending: string
  ready: string
  failed: string
}) {
  return (
    <li className="flex items-center gap-3 text-sm">
      <span
        aria-hidden="true"
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${state === 'ready' ? 'bg-green-100 text-green-700' : state === 'failed' ? 'bg-red-100 text-red-700' : 'bg-pale-blue text-blue'}`}
      >
        {state === 'ready' ? '✓' : state === 'failed' ? '!' : '·'}
      </span>
      <span
        className={
          state === 'ready'
            ? 'text-green-800'
            : state === 'failed'
              ? 'text-red-700'
              : 'text-slate-600'
        }
      >
        {state === 'ready' ? ready : state === 'failed' ? failed : pending}
      </span>
    </li>
  )
}

function videoProgressLabel(status: VideoStatus | null): string {
  if (status?.stage === 'planning') return 'Planning video...'
  if (status?.stage === 'narration') return 'Creating narration...'
  if (status?.stage === 'generating_clips')
    return `Creating video...${status.clips_total ? ` ${status.clips_done || 0} / ${status.clips_total} clips` : ''}`
  if (status?.stage === 'composing') return 'Composing final video...'
  return 'Video pending'
}

export default function PreviewPage({
  document,
  state,
  progress,
  selectedFormats,
  result,
  assets,
  assetError,
  videoStatus,
  videoUploads,
  mediaPreferences,
  analysis,
  master,
  error,
  retryLabel,
  onRetry,
  onBack,
  onNewDocument,
  onSave,
  onRegeneratePlatform,
  onChoosePrimaryMedia,
  onRemoveMedia,
  onRestoreGeneratedVideo,
  onRetryImage,
  onAddImages,
  onRegenerateVideo,
  onAddVideo,
}: {
  document: UploadResult
  state: PreviewState
  progress: PackageProgress
  selectedFormats: ContentType[]
  result: PlatformResult | null
  assets: AssetPack | null
  assetError: string
  videoStatus: VideoStatus | null
  videoUploads: UploadedVideo[]
  mediaPreferences: { primaryId: string | null; hideGeneratedVideo: boolean }
  analysis: SourceAnalysis | null
  master: MasterContent | null
  error: string
  retryLabel: string
  onRetry: () => void
  onBack: () => void
  onNewDocument: () => void
  onSave: (result: PlatformResult) => Promise<PlatformResult>
  onRegeneratePlatform: (platform: PlatformName) => Promise<void>
  onChoosePrimaryMedia: (item: MediaAsset) => Promise<void>
  onRemoveMedia: (item: MediaAsset, nextPrimaryId: string | null) => Promise<void>
  onRestoreGeneratedVideo: () => void
  onRetryImage: () => Promise<void>
  onAddImages: (files: File[]) => Promise<void>
  onRegenerateVideo: () => void
  onAddVideo: (file: File) => Promise<void>
}) {
  const [tab, setTab] = useState<PlatformName | null>(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<PlatformResult | null>(null)
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [showSources, setShowSources] = useState(false)
  const lastReadyVideo = useRef<{ runId: string; status: VideoStatus } | null>(null)

  const active = result && (tab && result.platforms.includes(tab) ? tab : result.platforms[0])
  const post = result?.items.find((item) => item.platform === active)
  const displayPost =
    post && result?.content_types.includes('video')
      ? {
          ...post,
          title: post.title || master?.headline || analysis?.title || '',
          body: post.body || master?.short_summary || analysis?.summary || '',
        }
      : post
  const editablePost = draft?.items.find((item) => item.platform === active)
  if (lastReadyVideo.current?.runId !== document.run_id) lastReadyVideo.current = null
  if (videoStatus?.stage === 'ready' && videoStatus.url)
    lastReadyVideo.current = { runId: document.run_id, status: videoStatus }
  const playableVideo =
    videoStatus?.stage === 'ready' ? videoStatus : lastReadyVideo.current?.status || null
  const imageSelected = result?.content_types.includes('image') || false
  const videoSelected = result?.content_types.includes('video') || false
  const media = orderedMediaAssets(
    assets,
    playableVideo,
    videoUploads,
    imageSelected,
    videoSelected,
    mediaPreferences.primaryId,
    mediaPreferences.hideGeneratedVideo,
  )

  function beginEdit() {
    if (!result) return
    setDraft({ ...result, items: result.items.map((item) => ({ ...item })) })
    setEditing(true)
    setSaveError('')
  }

  function updatePost(field: 'title' | 'body', value: string) {
    if (!active) return
    setDraft((current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.platform === active ? { ...item, [field]: value } : item,
            ),
          }
        : current,
    )
  }

  async function saveEdit() {
    if (!draft) return
    setSaving(true)
    setSaveError('')
    try {
      await onSave(draft)
      setEditing(false)
      setDraft(null)
    } catch (cause) {
      setSaveError(
        cause instanceof Error ? cause.message : 'Could not save this preview. Please retry.',
      )
    } finally {
      setSaving(false)
    }
  }

  async function regenerateCurrent() {
    if (!active) return
    setRegenerating(true)
    setSaveError('')
    try {
      await onRegeneratePlatform(active)
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : 'Could not regenerate this preview.')
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#fbfcfe] text-ink">
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
      <main className="mx-auto max-w-5xl px-6 pb-20 pt-9 sm:px-8 sm:pt-14">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-blue">
              Step 04 · Preview
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
              {state === 'ready'
                ? 'Your content is ready.'
                : state === 'error'
                  ? 'Generation paused.'
                  : 'Preparing your communication package'}
            </h1>
            <p className="mt-3 text-sm text-slate-500">{document.filename}</p>
          </div>
          {state === 'ready' && analysis && (
            <button
              onClick={() => setShowSources(true)}
              className="rounded-lg border border-[#d6e2f0] bg-white px-4 py-2 text-sm font-semibold text-blue hover:bg-[#f4f8fd]"
            >
              View sources
            </button>
          )}
        </div>

        {state !== 'ready' || !result ? (
          <section
            className="rounded-2xl border border-[#e5ebf3] bg-white px-6 py-10 shadow-[0_8px_30px_rgba(25,54,96,0.05)] sm:px-10"
            role="status"
            aria-label="Generation progress"
          >
            <h2 className="text-xl font-semibold">
              {state === 'error'
                ? 'A selected output could not be completed.'
                : 'Preparing your communication package'}
            </h2>
            <ul className="mt-7 space-y-4">
              <StageLine
                state={progress.source}
                pending="Understanding source..."
                ready="Source understood"
                failed="Source analysis failed"
              />
              <StageLine
                state={progress.platform}
                pending="Platform content pending"
                ready="Platform content ready"
                failed="Platform content failed"
              />
              {selectedFormats.includes('image') && (
                <StageLine
                  state={progress.image}
                  pending="Visuals pending"
                  ready="Visuals ready"
                  failed="Visual generation failed"
                />
              )}
              {selectedFormats.includes('video') && (
                <StageLine
                  state={progress.video}
                  pending={videoProgressLabel(videoStatus)}
                  ready="Video ready"
                  failed="Video generation failed"
                />
              )}
            </ul>
            {state === 'error' ? (
              <div className="mt-7">
                <p role="alert" className="text-sm text-red-700">
                  {error}
                </p>
                <button
                  onClick={onRetry}
                  className="mt-4 rounded-xl bg-blue px-5 py-3 text-sm font-semibold text-white hover:bg-[#123e85]"
                >
                  {retryLabel}
                </button>
              </div>
            ) : (
              <p className="mt-7 text-sm text-slate-500">This may take a few minutes.</p>
            )}
          </section>
        ) : (
          <section className="overflow-hidden rounded-2xl border border-[#e5ebf3] bg-white shadow-[0_8px_30px_rgba(25,54,96,0.05)]">
            <div
              className="flex overflow-x-auto border-b border-[#e8edf4] px-3 sm:px-6"
              role="tablist"
              aria-label="Platform previews"
            >
              {result.platforms.map((platform) => (
                <button
                  key={platform}
                  role="tab"
                  aria-selected={active === platform}
                  disabled={editing}
                  onClick={() => setTab(platform)}
                  className={`shrink-0 border-b-2 px-4 py-5 text-sm font-semibold ${active === platform ? 'border-blue text-blue' : 'border-transparent text-slate-500 hover:text-ink'} disabled:cursor-not-allowed`}
                >
                  {platformLabels[platform]}
                </button>
              ))}
            </div>
            <div className="p-6 sm:p-9">
              <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-[#edf1f6] pb-6">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue">
                    Final platform preview
                  </p>
                  <h2 className="mt-2 text-xl font-semibold">
                    {active ? platformLabels[active] : ''}
                  </h2>
                </div>
                {result.content_types.includes('text') && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => void regenerateCurrent()}
                      disabled={saving || regenerating || editing}
                      className="rounded-lg border border-[#d6e2f0] px-4 py-2 text-sm font-semibold text-blue hover:bg-[#f4f8fd] disabled:opacity-50"
                    >
                      {regenerating ? 'Regenerating...' : 'Regenerate platform content'}
                    </button>
                    <button
                      onClick={editing ? () => void saveEdit() : beginEdit}
                      disabled={saving || regenerating}
                      className="rounded-lg border border-[#d6e2f0] px-4 py-2 text-sm font-semibold text-blue hover:bg-[#f4f8fd] disabled:opacity-50"
                    >
                      {editing ? (saving ? 'Saving...' : 'Save') : 'Edit'}
                    </button>
                  </div>
                )}
              </div>
              {saveError && (
                <p
                  role="alert"
                  className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                >
                  {saveError}
                </p>
              )}
              {editing && result.content_types.includes('text') && post && (
                <div className="mb-7 space-y-5 rounded-xl border border-[#dce6f2] bg-[#f8fbff] p-5">
                  <p className="text-xs font-bold uppercase tracking-[0.15em] text-blue">
                    Edit platform text
                  </p>
                  <label className="block text-xs font-bold uppercase tracking-[0.15em] text-slate-500">
                    Title
                    <input
                      value={editablePost?.title || ''}
                      onChange={(event) => updatePost('title', event.target.value)}
                      className="mt-2 block w-full rounded-lg border border-[#cbd8e8] bg-white px-4 py-3 text-base font-semibold normal-case tracking-normal text-ink outline-none focus:border-blue"
                    />
                  </label>
                  <label className="block text-xs font-bold uppercase tracking-[0.15em] text-slate-500">
                    Text
                    <textarea
                      value={editablePost?.body || ''}
                      onChange={(event) => updatePost('body', event.target.value)}
                      rows={12}
                      className="mt-2 block w-full rounded-lg border border-[#cbd8e8] bg-white px-4 py-3 text-sm font-normal leading-7 normal-case tracking-normal text-ink outline-none focus:border-blue"
                    />
                  </label>
                </div>
              )}
              {active && displayPost && (
                <PlatformMockup
                  platform={active}
                  post={editing ? editablePost || displayPost : displayPost}
                  media={media}
                  video={videoSelected ? videoStatus : null}
                  documentType={analysis?.document_type}
                />
              )}
              {(imageSelected || videoSelected) && (
                <MediaAssets
                  media={media}
                  imageSelected={imageSelected}
                  videoSelected={videoSelected}
                  hideGeneratedVideo={mediaPreferences.hideGeneratedVideo}
                  videoStatus={videoStatus}
                  assetError={assetError || assets?.image_error || ''}
                  onChoosePrimary={onChoosePrimaryMedia}
                  onRemove={onRemoveMedia}
                  onRestoreGeneratedVideo={onRestoreGeneratedVideo}
                  onRetryImage={onRetryImage}
                  onRegenerateVideo={onRegenerateVideo}
                  onAddImages={onAddImages}
                  onAddVideo={onAddVideo}
                />
              )}
              {result.platforms.includes('youtube') &&
                playableVideo?.stage === 'ready' &&
                playableVideo.url && (
                  <YouTubePublisher
                    runId={document.run_id}
                    title={result.items.find((item) => item.platform === 'youtube')?.title || ''}
                    description={
                      result.items.find((item) => item.platform === 'youtube')?.body || ''
                    }
                    disabled={editing || saving}
                  />
                )}
              {result.platforms.includes('tiktok') &&
                playableVideo?.stage === 'ready' &&
                playableVideo.url && (
                  <TikTokPublisher runId={document.run_id} disabled={editing || saving} />
                )}
              {result.platforms.includes('facebook') && (
                <MetaPublisher
                  platform="facebook"
                  runId={document.run_id}
                  primaryMediaId={media.find((item) => item.primary)?.id || null}
                  disabled={editing || saving}
                />
              )}
              {result.platforms.includes('instagram') && (
                <MetaPublisher
                  platform="instagram"
                  runId={document.run_id}
                  primaryMediaId={media.find((item) => item.primary)?.id || null}
                  disabled={editing || saving}
                />
              )}
              {result.platforms.includes('website') && (
                <UniversityPublisher
                  runId={document.run_id}
                  media={media}
                  disabled={editing || saving}
                />
              )}
            </div>
          </section>
        )}
        <button
          onClick={onBack}
          disabled={state === 'waiting'}
          className="mt-7 text-sm font-semibold text-slate-500 hover:text-blue disabled:opacity-40"
        >
          ← Back to platforms
        </button>
      </main>
      <footer className="mx-auto flex max-w-6xl items-center justify-between border-t border-[#edf1f5] px-6 py-6 text-xs text-slate-400 sm:px-8">
        <span>UD PR Studio</span>
        <span>Platform previews</span>
      </footer>
      {showSources && analysis && (
        <SourcesModal analysis={analysis} onClose={() => setShowSources(false)} />
      )}
    </div>
  )
}
