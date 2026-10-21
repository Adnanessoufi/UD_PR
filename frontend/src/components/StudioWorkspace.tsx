import { useEffect, useRef, useState, type ReactNode } from 'react'
import PlatformMockup from './PlatformMockup'
import PublishPanel from './PublishPanel'
import SourcesModal from './SourcesModal'
import VerificationPanel from './VerificationPanel'
import MasterReviewPanel from './MasterReviewPanel'
import type { ReviewStatus } from '../types/verification'
import CampaignLibrary from './CampaignLibrary'
import CampaignBriefPanel from './CampaignBriefPanel'
import NewsPanel from './NewsPanel'
import ExportPanel from './ExportPanel'
import ExtensionSlot from '../extensions/ExtensionSlot'
import type { ExtensionContext } from '../extensions/types'
import type { CampaignBrief } from '../types/campaign'
import StudioMediaTray from './StudioMediaTray'
import { uploadDocument } from '../services/upload'
import type { AssetPack } from '../types/assets'
import type { CombinedResult, MasterContent } from '../types/content'
import type { PackageProgress, StageState, ProcessingState } from '../types/generation'
import { orderedMediaAssets, type MediaAsset } from '../types/media'
import {
  platformAvailability,
  platformLabels,
  type ContentType,
  type OutputLanguage,
  type PlatformName,
  type PlatformResult,
} from '../types/platform'
import type { UploadResult } from '../types/upload'
import type { UploadedVideo, VideoStatus } from '../types/video'

type Screen = 'upload' | 'formats' | 'platforms' | 'preview'
type PreviewState = 'waiting' | 'ready' | 'error'
type MediaPreferences = { primaryId: string | null; hideGeneratedVideo: boolean }
type Props = {
  demo?: {
    tools: ReactNode
    story: ReactNode
    review: ReactNode
    exports: ReactNode
    onCampaigns: () => void
    onChooseSource: () => void
  }
  brief: CampaignBrief
  onSaveBrief: (brief: CampaignBrief) => Promise<void>
  onOpenCampaign: (id: string) => Promise<void>
  workspaceError: string
  restoring: boolean
  sourceMode: 'document' | 'quick' | 'news'
  quickStage: string
  onSourceModeChange: (mode: 'document' | 'quick' | 'news') => void
  language: OutputLanguage
  onLanguageChange: (language: OutputLanguage) => void
  onGenerateQuick: (sentence: string) => Promise<void>
  screen: Screen
  document: UploadResult | null
  formats: ContentType[]
  platforms: PlatformName[]
  processing: ProcessingState
  processingError: string
  combined: CombinedResult | null
  preview: PlatformResult | null
  previewState: PreviewState
  progress: PackageProgress
  errorMessage: string
  retryLabel: string
  assets: AssetPack | null
  assetError: string
  videoStatus: VideoStatus | null
  videoUploads: UploadedVideo[]
  mediaPreferences: MediaPreferences
  onUploaded: (uploaded: UploadResult) => void
  onNewDocument: () => void
  onRetryAnalysis: () => void
  onToggleFormat: (format: ContentType) => void
  onTogglePlatform: (platform: PlatformName) => void
  onGenerate: () => void
  onRetryPreview: () => void
  onSave: (result: PlatformResult) => Promise<PlatformResult>
  onSaveMaster: (content: MasterContent) => Promise<void>
  onRegeneratePlatform: (platform: PlatformName) => Promise<void>
  onChoosePrimaryMedia: (item: MediaAsset) => Promise<void>
  onRemoveMedia: (item: MediaAsset, nextPrimaryId: string | null) => Promise<void>
  onRestoreGeneratedVideo: () => void
  onRetryImage: () => Promise<void>
  onAddImages: (files: File[]) => Promise<void>
  onRegenerateVideo: () => void
  onAddVideo: (file: File) => Promise<void>
  onDeleteVideo: (id: string) => Promise<void>
}

const destinationOrder: PlatformName[] = [
  'website',
  'linkedin',
  'facebook',
  'instagram',
  'tiktok',
  'youtube',
]
const outputOptions: { id: ContentType; label: string; description: string }[] = [
  { id: 'text', label: 'Text', description: 'An article and posts for your channels' },
  { id: 'image', label: 'Image', description: 'Images to go with your story' },
  { id: 'video', label: 'Video', description: 'A video with narration and captions' },
]
const quickStageLabels: Record<string, string> = {
  starting: 'Starting research...',
  researching_announcement: 'Researching announcement...',
  finding_official_sources: 'Finding official sources...',
  finding_relevant_visuals: 'Finding relevant visuals...',
  preparing_communication_package: 'Preparing your drafts...',
}

function ConnectionMark({ name }: { name: PlatformName }) {
  if (name === 'website')
    return <img className="ud-platform-logo website" src="/ud-logo.png" alt="" aria-hidden="true" />
  if (name === 'instagram')
    return (
      <img
        className="ud-platform-logo instagram"
        src="/instagram-logo.svg"
        alt=""
        aria-hidden="true"
      />
    )
  const glyph: Record<PlatformName, string> = {
    website: '◎',
    facebook: 'f',
    instagram: '◎',
    tiktok: '♪',
    youtube: '▶',
    linkedin: 'in',
  }
  return (
    <span className={`ud-platform-mark ${name}`} aria-hidden="true">
      {glyph[name]}
    </span>
  )
}

function ProgressRow({
  label,
  state,
  detail,
}: {
  label: string
  state: StageState
  detail?: string
}) {
  return (
    <div className="ud-progress-row">
      <span>{label}</span>
      <strong className={state}>
        {state === 'ready' ? 'Complete' : state === 'failed' ? 'Failed' : detail || 'Preparing...'}
      </strong>
    </div>
  )
}

function videoDetail(status: VideoStatus | null): string {
  if (status?.stage === 'generating_clips')
    return `Generating ${status.clips_done || 0} / ${status.clips_total || '?'} clips`
  if (status?.stage === 'planning') return 'Planning video...'
  if (status?.stage === 'narration') return 'Creating narration...'
  if (status?.stage === 'composing') return 'Composing video...'
  return 'Preparing...'
}

export default function StudioWorkspace(props: Props) {
  const {
    screen,
    document,
    formats,
    platforms,
    processing,
    processingError,
    combined,
    preview,
    previewState,
    progress,
    errorMessage,
    retryLabel,
    assets,
    assetError,
    videoStatus,
    videoUploads,
    mediaPreferences,
  } = props
  const [showLibrary, setShowLibrary] = useState(false)
  const [masterEditing, setMasterEditing] = useState(false)
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus | null>(null)
  const [view, setView] = useState<'source' | 'review' | 'publish'>('source')
  const [activeTab, setActiveTab] = useState<PlatformName | null>(null)
  const [connections, setConnections] = useState<
    Record<'facebook' | 'instagram' | 'tiktok' | 'youtube', boolean | null>
  >({ facebook: null, instagram: null, tiktok: null, youtube: null })
  const [uploading, setUploading] = useState(false)
  const [uploadPercent, setUploadPercent] = useState(0)
  const [uploadError, setUploadError] = useState('')
  const [quickText, setQuickText] = useState('')
  const [showSources, setShowSources] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<PlatformResult | null>(null)
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [actionError, setActionError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const lastReadyVideo = useRef<{
    runId: string
    language: OutputLanguage
    status: VideoStatus
  } | null>(null)

  useEffect(() => {
    if (props.demo) return
    const controller = new AbortController()
    void Promise.allSettled([
      fetch('/api/meta/status', { signal: controller.signal }).then(
        (response) =>
          response.json() as Promise<{
            facebook_connected?: boolean
            instagram_connected?: boolean
          }>,
      ),
      fetch('/api/tiktok/status', { signal: controller.signal }).then(
        (response) => response.json() as Promise<{ connected?: boolean }>,
      ),
      fetch('/api/youtube/status', { signal: controller.signal }).then(
        (response) => response.json() as Promise<{ connected?: boolean }>,
      ),
    ]).then((results) => {
      if (controller.signal.aborted) return
      const meta = results[0].status === 'fulfilled' ? results[0].value : null
      const tiktok = results[1].status === 'fulfilled' ? results[1].value : null
      const youtube = results[2].status === 'fulfilled' ? results[2].value : null
      setConnections({
        facebook: Boolean(meta?.facebook_connected),
        instagram: Boolean(meta?.instagram_connected),
        tiktok: Boolean(tiktok?.connected),
        youtube: Boolean(youtube?.connected),
      })
    })
    return () => controller.abort()
  }, [])

  const ready = screen === 'preview' && previewState === 'ready' && Boolean(preview)
  const generating = screen === 'preview' && !ready
  useEffect(() => {
    if (ready) setView('review')
    else setView('source')
  }, [ready, document?.run_id])
  if (
    lastReadyVideo.current?.runId !== document?.run_id ||
    lastReadyVideo.current?.language !== props.language
  )
    lastReadyVideo.current = null
  if (
    document &&
    videoStatus?.stage === 'ready' &&
    videoStatus.url &&
    (videoStatus.language || 'en') === props.language
  )
    lastReadyVideo.current = {
      runId: document.run_id,
      language: props.language,
      status: videoStatus,
    }
  const playableVideo =
    videoStatus?.stage === 'ready' && (videoStatus.language || 'en') === props.language
      ? videoStatus
      : lastReadyVideo.current?.status || null
  const imageSelected = preview?.content_types.includes('image') || false
  const videoSelected = preview?.content_types.includes('video') || false
  const media = orderedMediaAssets(
    assets,
    playableVideo,
    videoUploads,
    imageSelected,
    videoSelected,
    mediaPreferences.primaryId,
    mediaPreferences.hideGeneratedVideo,
  )
  const reviewContext = {
    platforms: preview?.platforms || [],
    primary_media_id: media.find((item) => item.primary)?.id || null,
    media_ids: media.map((item) => item.id),
  }
  const reviewKey = JSON.stringify({
    preview,
    master: combined?.content,
    media,
    video: videoStatus?.stage,
  })
  useEffect(() => {
    setReviewStatus(null)
  }, [reviewKey])
  const mediaReady =
    (!imageSelected || progress.image === 'ready') && (!videoSelected || progress.video === 'ready')
  const approved =
    reviewStatus?.state === 'approved' && mediaReady && !editing && !masterEditing && !regenerating
  const tabs = destinationOrder.filter((item) => preview?.platforms.includes(item))
  const hasPublishDestinations = tabs.some(
    (item) =>
      item === 'website' ||
      item === 'facebook' ||
      item === 'instagram' ||
      item === 'youtube' ||
      (item === 'tiktok' && videoSelected),
  )
  const active = activeTab && tabs.includes(activeTab) ? activeTab : tabs[0]
  const post = preview?.items.find((item) => item.platform === active)
  const displayPost =
    post && videoSelected
      ? {
          ...post,
          title: post.title || combined?.content.headline || '',
          body: post.body || combined?.content.short_summary || '',
        }
      : post
  const editedPost = draft?.items.find((item) => item.platform === active)
  const extensionContext: ExtensionContext = {
    runId: document?.run_id || null,
    language: props.language,
    brief: props.brief,
    combined,
    preview,
    media,
    saveMaster: props.onSaveMaster,
    saveBrief: props.onSaveBrief,
  }
  const phase = generating ? 'create' : ready ? view : 'source'
  const quickValid = quickText.trim().length >= 8
  const sourceReady =
    props.sourceMode === 'quick' ? quickValid || Boolean(document) : Boolean(document)

  useEffect(() => {
    if (props.sourceMode === 'quick' && document && combined)
      setQuickText(combined.analysis.key_facts[0]?.statement || '')
  }, [document?.run_id])

  async function chooseFile(file: File | undefined) {
    if (!file) return
    setUploadError('')
    if (!/\.(pdf|docx)$/i.test(file.name) || file.size === 0) {
      setUploadError('Choose a PDF or DOCX with some content in it.')
      return
    }
    setUploading(true)
    setUploadPercent(0)
    try {
      props.onUploaded(await uploadDocument(file, setUploadPercent))
      setView('source')
    } catch (cause) {
      setUploadError(cause instanceof Error ? cause.message : 'Document upload failed.')
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }
  function startEdit() {
    if (!preview) return
    setDraft({ ...preview, items: preview.items.map((item) => ({ ...item })) })
    setEditing(true)
    setActionError('')
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
    setActionError('')
    try {
      await props.onSave(draft)
      setEditing(false)
      setDraft(null)
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Could not save text.')
    } finally {
      setSaving(false)
    }
  }
  async function regenerateText() {
    if (!active) return
    setRegenerating(true)
    setActionError('')
    try {
      await props.onRegeneratePlatform(active)
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Could not regenerate text.')
    } finally {
      setRegenerating(false)
    }
  }
  function newPackage() {
    props.onNewDocument()
    setQuickText('')
    setView('source')
    setActiveTab(null)
    setEditing(false)
    setMasterEditing(false)
    setDraft(null)
  }

  return (
    <div className="ud-studio">
      <header className="ud-header">
        <div className="ud-header-inner">
          <button
            type="button"
            className="ud-identity"
            onClick={() => (ready ? setView('source') : undefined)}
            aria-label="UD PR Studio source"
          >
            <img src="/ud-logo.png" alt="University of Debrecen emblem" />
            <span>
              <strong>UNIVERSITY OF DEBRECEN</strong>
              <small>PR Studio</small>
            </span>
          </button>
          <button
            type="button"
            className="ud-secondary-button"
            onClick={props.demo ? props.demo.onCampaigns : () => setShowLibrary(true)}
          >
            Campaigns
          </button>
          <div className="ud-connections">
            {(['facebook', 'instagram', 'tiktok', 'youtube'] as const).map((name) => (
              <div key={name} className="ud-connection">
                <ConnectionMark name={name} />
                <span>
                  <strong>{platformLabels[name]}</strong>
                  <small>
                    {props.demo
                      ? 'Demo only'
                      : connections[name] === null
                        ? 'Checking'
                        : connections[name]
                          ? 'Connected'
                          : 'Not connected'}
                  </small>
                </span>
              </div>
            ))}
          </div>
        </div>
      </header>
      <nav className="ud-workflow" aria-label="Workflow">
        <div className="ud-workflow-inner">
          {(
            [
              ['source', 'Source'],
              ['create', 'Create'],
              ['review', 'Review'],
              ['publish', 'Publish'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={phase === id ? 'active' : ''}
              aria-current={phase === id ? 'step' : undefined}
              disabled={
                id === 'create' ||
                ((id === 'review' || id === 'publish') && !ready) ||
                (id === 'publish' && (!hasPublishDestinations || !approved))
              }
              onClick={() =>
                setView(id === 'publish' ? 'publish' : id === 'review' ? 'review' : 'source')
              }
            >
              {label}
            </button>
          ))}
        </div>
      </nav>
      <main className="ud-main">
        {props.demo?.tools}
        {props.workspaceError && (
          <p role="alert" className="ud-error workspace-workspace-error">
            {props.workspaceError}
          </p>
        )}
        {props.restoring && (
          <p role="status" className="ud-source-note">
            Restoring your campaign…
          </p>
        )}
        {generating ? (
          <section className="ud-progress-screen" role="status">
            <p className="ud-eyebrow">02 / Create</p>
            <h1>{previewState === 'error' ? 'Generation paused' : 'Preparing your campaign'}</h1>
            <p>Your drafts will appear here when they're ready.</p>
            <div className="ud-progress-list">
              <ProgressRow
                label={props.sourceMode === 'quick' ? 'Web research' : 'Source understood'}
                state={progress.source}
                detail={
                  props.sourceMode === 'quick' ? quickStageLabels[props.quickStage] : undefined
                }
              />
              <ProgressRow label="Platform content" state={progress.platform} />
              {formats.includes('image') && (
                <ProgressRow label="Visual assets" state={progress.image} />
              )}
              {formats.includes('video') && (
                <ProgressRow
                  label="Video"
                  state={progress.video}
                  detail={videoDetail(videoStatus)}
                />
              )}
            </div>
            {previewState === 'error' ? (
              <>
                <p className="ud-error" role="alert">
                  {errorMessage}
                </p>
                <button type="button" className="ud-primary-button" onClick={props.onRetryPreview}>
                  {retryLabel}
                </button>
              </>
            ) : (
              <p className="ud-progress-note">This may take a few minutes.</p>
            )}
          </section>
        ) : ready && view === 'publish' && preview && document ? (
          <div className="ud-publish-screen">
            <PublishPanel
              key={`${document.run_id}:${preview.language}`}
              runId={document.run_id}
              preview={preview}
              media={media}
              approved={approved}
            />
            <button type="button" className="ud-text-button" onClick={() => setView('review')}>
              ← Back to review
            </button>
          </div>
        ) : ready && view === 'review' && preview ? (
          <div className="ud-review-screen">
            <div className="ud-section-heading">
              <p className="ud-eyebrow">03 / Review</p>
              <h1>Have a look at your campaign</h1>
              <p>Read the drafts and check the media before you publish.</p>
            </div>
            {combined?.analysis.warning && (
              <p className="ud-research-warning" role="status">
                {combined.analysis.warning}
              </p>
            )}
            <div className="ud-review-tabs" role="tablist" aria-label="Platform preview">
              {tabs.map((platform) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={active === platform}
                  key={platform}
                  className={active === platform ? 'active' : ''}
                  disabled={editing}
                  onClick={() => setActiveTab(platform)}
                >
                  {platformLabels[platform]}
                </button>
              ))}
            </div>
            <div className="ud-review-actions">
              <span>{active ? `${platformLabels[active]} preview` : 'Platform preview'}</span>
              <div>
                {combined && (
                  <button type="button" onClick={() => setShowSources(true)}>
                    {combined.analysis.document_type === 'quick_announcement'
                      ? 'View research sources'
                      : 'Sources'}
                  </button>
                )}
                {
                  <>
                    <button
                      type="button"
                      disabled={regenerating || editing || Boolean(props.demo)}
                      title={
                        props.demo ? 'Live generation is available in the full app.' : undefined
                      }
                      onClick={() => void regenerateText()}
                    >
                      {regenerating ? 'Regenerating...' : 'Regenerate text'}
                    </button>
                    <button
                      type="button"
                      disabled={saving || regenerating}
                      onClick={editing ? () => void saveEdit() : startEdit}
                    >
                      {editing ? (saving ? 'Saving...' : 'Save text') : 'Edit text'}
                    </button>
                    {editing && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(false)
                          setDraft(null)
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </>
                }
              </div>
            </div>
            {actionError && (
              <p role="alert" className="ud-error">
                {actionError}
              </p>
            )}
            {editing && editedPost && (
              <div className="ud-editor">
                <label>
                  Headline
                  <input
                    value={editedPost.title}
                    onChange={(event) => updatePost('title', event.target.value)}
                  />
                </label>
                <label>
                  Body
                  <textarea
                    rows={8}
                    value={editedPost.body}
                    onChange={(event) => updatePost('body', event.target.value)}
                  />
                </label>
              </div>
            )}
            {props.demo ? (
              props.demo.story
            ) : (
              <ExtensionSlot name="review.top" context={extensionContext} />
            )}
            <div className="ud-preview-stage">
              {active && displayPost && (
                <PlatformMockup
                  platform={active}
                  post={editing ? editedPost || displayPost : displayPost}
                  media={media}
                  video={videoSelected ? videoStatus : null}
                  documentType={combined?.analysis.document_type}
                />
              )}
            </div>
            {combined?.analysis.document_type === 'quick_announcement' &&
              combined.analysis.research_sources &&
              combined.analysis.research_sources.length > 0 && (
                <div className="ud-research-citations">
                  <strong>Research sources:</strong>{' '}
                  {combined.analysis.research_sources.slice(0, 3).map((source, index) => (
                    <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer">
                      [{index + 1}] {source.domain}
                    </a>
                  ))}
                </div>
              )}
            {(imageSelected || videoSelected) && (
              <StudioMediaTray
                media={media}
                sampleMode={Boolean(props.demo)}
                imageSelected={imageSelected}
                videoSelected={videoSelected}
                hideGeneratedVideo={mediaPreferences.hideGeneratedVideo}
                videoStatus={videoStatus}
                assetError={assetError || assets?.image_error || ''}
                onChoosePrimary={props.onChoosePrimaryMedia}
                onRemove={props.onRemoveMedia}
                onRestoreGeneratedVideo={props.onRestoreGeneratedVideo}
                onRetryImage={props.onRetryImage}
                onRegenerateVideo={props.onRegenerateVideo}
                onAddImages={props.onAddImages}
                onAddVideo={props.onAddVideo}
              />
            )}
            {!mediaReady && (
              <div className="workspace-media-progress">
                <p className="ud-source-note">
                  You can read the drafts while the media is being prepared. You can approve the
                  campaign once the media is ready too.
                </p>
                {imageSelected && <ProgressRow label="Images" state={progress.image} />}
                {videoSelected && (
                  <ProgressRow
                    label="Video"
                    state={progress.video}
                    detail={videoDetail(videoStatus)}
                  />
                )}
                {(progress.image === 'failed' || progress.video === 'failed') && (
                  <button
                    type="button"
                    className="ud-secondary-button"
                    onClick={props.onRetryPreview}
                  >
                    Retry media
                  </button>
                )}
              </div>
            )}
            <ExtensionSlot name="review.tools" context={extensionContext} />
            {props.demo
              ? props.demo.exports
              : document && <ExportPanel runId={document.run_id} preview={preview} />}
            {combined && (
              <MasterReviewPanel
                content={combined.content}
                onSave={props.onSaveMaster}
                onEditingChange={setMasterEditing}
              />
            )}
            {props.demo
              ? props.demo.review
              : document && (
                  <VerificationPanel
                    runId={document.run_id}
                    context={reviewContext}
                    revisionKey={reviewKey}
                    editing={editing || masterEditing || saving || regenerating || !mediaReady}
                    onStatus={setReviewStatus}
                  />
                )}
            {hasPublishDestinations && (
              <div className="ud-review-next">
                <button
                  type="button"
                  className="ud-primary-button"
                  disabled={!approved}
                  onClick={() => setView('publish')}
                >
                  Continue to publish →
                </button>
              </div>
            )}
          </div>
        ) : (
          <section className="ud-source-screen">
            <div className="ud-section-heading">
              <p className="ud-eyebrow">01 / Source</p>
              <h1>What would you like to share?</h1>
              <p>
                {props.sourceMode === 'quick'
                  ? 'Start with a short announcement. Choose the channels you want drafts for below.'
                  : props.sourceMode === 'news'
                    ? 'Pick a news story, then choose who you want to share it with.'
                    : 'Upload a document, then choose what you want to make from it.'}
              </p>
            </div>
            <div className="ud-source-modes" role="tablist" aria-label="Source mode">
              <button
                type="button"
                role="tab"
                aria-selected={props.sourceMode === 'document'}
                className={props.sourceMode === 'document' ? 'active' : ''}
                onClick={() => props.onSourceModeChange('document')}
              >
                Document
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={props.sourceMode === 'news'}
                className={props.sourceMode === 'news' ? 'active' : ''}
                disabled={Boolean(props.demo)}
                title={props.demo ? 'News import is available in the full app.' : undefined}
                onClick={() => props.onSourceModeChange('news')}
              >
                News inbox
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={props.sourceMode === 'quick'}
                className={props.sourceMode === 'quick' ? 'active' : ''}
                disabled={Boolean(props.demo)}
                title={
                  props.demo
                    ? 'Live announcements are available in the full app. Use the prepared announcement sample above.'
                    : undefined
                }
                onClick={() => props.onSourceModeChange('quick')}
              >
                Quick announcement
              </button>
            </div>
            {props.sourceMode === 'news' ? (
              <>
                <NewsPanel onCollected={props.onUploaded} />
                {document && <p className="ud-source-note">Selected story: {document.filename}</p>}
                {document && processing === 'processing' && (
                  <p role="status" className="ud-source-note">
                    Reading the article…
                  </p>
                )}
                {document && processing === 'failed' && (
                  <p role="alert" className="ud-error">
                    {processingError}{' '}
                    <button type="button" onClick={props.onRetryAnalysis}>
                      Retry analysis
                    </button>
                  </p>
                )}
              </>
            ) : props.sourceMode === 'document' ? (
              <div className="ud-source-section">
                <h2>Upload document</h2>
                <div className="ud-upload-row">
                  <div className="ud-document-icon">
                    {props.demo ? 'TXT' : document?.file_type === 'docx' ? 'DOC' : 'PDF'}
                  </div>
                  <div>
                    <strong>
                      {document?.filename || 'Choose a paper or another university document'}
                    </strong>
                    <small>
                      {uploading
                        ? `${uploadPercent}% uploaded`
                        : document
                          ? props.demo
                            ? 'Prepared sample source'
                            : `${document.file_type.toUpperCase()} · Uploaded${document.cached ? ' · Saved source' : ''}`
                          : 'PDF or DOCX'}
                    </small>
                  </div>
                  <button
                    type="button"
                    className="ud-secondary-button"
                    disabled={uploading}
                    onClick={
                      props.demo ? props.demo.onChooseSource : () => fileInput.current?.click()
                    }
                  >
                    {document ? 'Replace' : 'Browse'}
                  </button>
                  <input
                    ref={fileInput}
                    type="file"
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    className="sr-only"
                    aria-label="Select source document"
                    onChange={(event) => void chooseFile(event.target.files?.[0])}
                  />
                </div>
                {uploading && (
                  <progress value={uploadPercent} max={100} className="ud-upload-progress" />
                )}
                {uploadError && (
                  <p className="ud-error" role="alert">
                    {uploadError}
                  </p>
                )}
                {document && processing === 'processing' && (
                  <p className="ud-source-note">Reading your document...</p>
                )}
                {document && processing === 'failed' && (
                  <p className="ud-error" role="alert">
                    {processingError}{' '}
                    <button type="button" onClick={props.onRetryAnalysis}>
                      Retry analysis
                    </button>
                  </p>
                )}
              </div>
            ) : (
              <div className="ud-source-section">
                <h2>Your announcement</h2>
                <label className="ud-quick-label" htmlFor="ud-quick-text">
                  Write one short sentence
                </label>
                <textarea
                  id="ud-quick-text"
                  className="ud-quick-textarea"
                  rows={3}
                  maxLength={500}
                  value={quickText}
                  readOnly={Boolean(props.demo)}
                  onChange={(event) => setQuickText(event.target.value)}
                />
                <p className="ud-source-note">
                  We'll look for public sources and images to go with it. Check any research
                  warnings before you publish.
                </p>
              </div>
            )}
            <CampaignBriefPanel
              brief={props.brief}
              disabled={uploading || !sourceReady}
              onSave={props.onSaveBrief}
            />
            <ExtensionSlot name="source.tools" context={extensionContext} />
            <div className="ud-source-section">
              <h2>What should we create?</h2>
              <div className="ud-output-list">
                {outputOptions
                  .filter((option) => props.sourceMode !== 'quick' || option.id !== 'video')
                  .map((option) => (
                    <label
                      key={option.id}
                      className={`ud-choice ${formats.includes(option.id) ? 'selected' : ''} ${props.sourceMode === 'quick' && option.id === 'text' ? 'ud-choice-required' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={formats.includes(option.id)}
                        disabled={
                          (props.sourceMode === 'quick' && option.id === 'text') ||
                          !sourceReady ||
                          uploading
                        }
                        onChange={() => props.onToggleFormat(option.id)}
                      />
                      <span>
                        <strong>{option.label}</strong>
                        <small>{option.description}</small>
                      </span>
                    </label>
                  ))}
              </div>
              {props.sourceMode === 'quick' && (
                <p className="ud-source-note">
                  Text is already included. Choose Image if you want visuals too. Video isn't
                  available for quick announcements.
                </p>
              )}
            </div>
            <div className="ud-source-section">
              <h2>Where should it go?</h2>
              <div className="ud-destination-list">
                {destinationOrder.map((platform) => {
                  const availability = platformAvailability(
                    platform,
                    formats,
                    props.sourceMode === 'quick',
                  )
                  return (
                    <label
                      key={platform}
                      className={`ud-destination ${platforms.includes(platform) ? 'selected' : ''}`}
                      title={!availability.enabled ? availability.reason : undefined}
                    >
                      <input
                        type="checkbox"
                        checked={platforms.includes(platform)}
                        disabled={!sourceReady || !availability.enabled}
                        onChange={() => props.onTogglePlatform(platform)}
                      />
                      <ConnectionMark name={platform} />
                      <span>{platformLabels[platform]}</span>
                    </label>
                  )
                })}
              </div>
            </div>
            <div className="ud-source-section">
              <h2>Language</h2>
              <div className="ud-language-options" role="group" aria-label="Output language">
                <button
                  type="button"
                  className={props.language === 'en' ? 'selected' : ''}
                  aria-pressed={props.language === 'en'}
                  onClick={() => props.onLanguageChange('en')}
                >
                  English
                </button>
                <button
                  type="button"
                  className={props.language === 'hu' ? 'selected' : ''}
                  aria-pressed={props.language === 'hu'}
                  onClick={() => props.onLanguageChange('hu')}
                >
                  Magyar
                </button>
              </div>
            </div>
            <div className="ud-source-actions">
              <button
                type="button"
                className="ud-primary-button"
                disabled={!sourceReady || !formats.length || !platforms.length || uploading}
                onClick={
                  props.sourceMode === 'quick' &&
                  (!document ||
                    quickText.trim() !== combined?.analysis.key_facts[0]?.statement.trim())
                    ? () => void props.onGenerateQuick(quickText.trim())
                    : ready
                      ? () => setView('review')
                      : props.onGenerate
                }
              >
                {ready
                  ? 'Review campaign'
                  : props.demo
                    ? 'Open sample campaign'
                    : 'Generate campaign'}
              </button>
              {document && (
                <button type="button" className="ud-text-button" onClick={newPackage}>
                  Start a new package
                </button>
              )}
            </div>
          </section>
        )}
      </main>
      <footer className="ud-footer">
        <span>University of Debrecen · PR Studio</span>
        <span>Internal communications workspace</span>
      </footer>
      {showLibrary && (
        <CampaignLibrary onOpen={props.onOpenCampaign} onClose={() => setShowLibrary(false)} />
      )}
      {showSources && combined && (
        <SourcesModal
          analysis={combined.analysis}
          sample={Boolean(props.demo)}
          onClose={() => setShowSources(false)}
        />
      )}
    </div>
  )
}
