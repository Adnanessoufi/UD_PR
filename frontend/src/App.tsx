import { useEffect, useRef, useState } from 'react'
import StudioWorkspace from './components/StudioWorkspace'
import { reopenCampaign, saveBrief, saveWorkspace } from './services/campaigns'
import { defaultBrief, type CampaignBrief } from './types/campaign'
import {
  deleteAsset,
  generateAssets,
  regenerateImage,
  setMainAsset,
  uploadImage,
} from './services/assets'
import {
  createQuickAnnouncement,
  loadSaved,
  processDocument,
  quickAnnouncementStatus,
  saveMaster,
} from './services/content'
import { generatePlatforms, regeneratePlatform, savePlatforms } from './services/platforms'
import {
  deleteVideo,
  getVideoStatus,
  listVideoUploads,
  regenerateVideo,
  startVideo,
  uploadVideo,
} from './services/video'
import type { CombinedResult, MasterContent } from './types/content'
import type { AssetPack } from './types/assets'
import { packageState, type PackageProgress, type ProcessingState } from './types/generation'
import type { MediaAsset } from './types/media'
import {
  platformAvailability,
  platformOrder,
  type ContentType,
  type OutputLanguage,
  type PlatformName,
  type PlatformResult,
} from './types/platform'
import type { UploadResult } from './types/upload'
import type { UploadedVideo, VideoStatus } from './types/video'

type Screen = 'upload' | 'formats' | 'platforms' | 'preview'
type MediaPreferences = { primaryId: string | null; hideGeneratedVideo: boolean }
const emptyMediaPreferences: MediaPreferences = { primaryId: null, hideGeneratedVideo: false }

function readMediaPreferences(runId: string): MediaPreferences {
  try {
    const saved = JSON.parse(localStorage.getItem(`ud-pr-media:${runId}`) || '{}')
    return {
      primaryId: typeof saved.primaryId === 'string' ? saved.primaryId : null,
      hideGeneratedVideo: saved.hideGeneratedVideo === true,
    }
  } catch {
    return emptyMediaPreferences
  }
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('upload')
  const [document, setDocument] = useState<UploadResult | null>(null)
  const [sourceMode, setSourceMode] = useState<'document' | 'quick' | 'news'>('document')
  const [brief, setBrief] = useState<CampaignBrief>(defaultBrief)
  const [workspaceError, setWorkspaceError] = useState('')
  const [restoring, setRestoring] = useState(false)
  const restoredOnce = useRef(false)
  const [language, setLanguage] = useState<OutputLanguage>('en')
  const [quickStage, setQuickStage] = useState('starting')
  const [formats, setFormats] = useState<ContentType[]>([])
  const [platforms, setPlatforms] = useState<PlatformName[]>([])
  const [processing, setProcessing] = useState<ProcessingState>('processing')
  const [processingError, setProcessingError] = useState('')
  const [combined, setCombined] = useState<CombinedResult | null>(null)
  const [preview, setPreview] = useState<PlatformResult | null>(null)
  const [assetPack, setAssetPack] = useState<AssetPack | null>(null)
  const [assetError, setAssetError] = useState('')
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null)
  const [videoUploads, setVideoUploads] = useState<UploadedVideo[]>([])
  const [mediaPreferences, setMediaPreferences] = useState<MediaPreferences>(emptyMediaPreferences)
  const [previewError, setPreviewError] = useState('')
  const [retryStage, setRetryStage] = useState<'analysis' | 'platform'>('analysis')
  const activeRun = useRef<string | null>(null)
  const processingRequest = useRef<{ runId: string; promise: Promise<CombinedResult> } | null>(null)
  const combinedResult = useRef<CombinedResult | null>(null)
  const generating = useRef<string | null>(null)
  const videoRetryForce = useRef(false)
  const quickSentence = useRef('')
  useEffect(() => {
    if (restoredOnce.current) return
    restoredOnce.current = true
    const last = localStorage.getItem('ud-pr-active-run')
    if (last)
      void openCampaign(last).catch(() => {
        localStorage.removeItem('ud-pr-active-run')
      })
  }, [])

  useEffect(() => {
    if (!document || restoring) return
    const timer = window.setTimeout(() => {
      void saveWorkspace(document.run_id, { content_types: formats, platforms, language }).catch(
        (cause) =>
          setWorkspaceError(
            cause instanceof Error ? cause.message : 'Workspace could not be saved.',
          ),
      )
    }, 500)
    return () => window.clearTimeout(timer)
  }, [document?.run_id, formats, platforms, language, restoring])

  async function openCampaign(id: string) {
    setRestoring(true)
    setWorkspaceError('')
    try {
      const data = await reopenCampaign(id)
      activeRun.current = id
      generating.current = null
      processingRequest.current = null
      combinedResult.current = data.combined
      setDocument(data.run)
      setSourceMode(
        data.run.file_type === 'announcement'
          ? 'quick'
          : data.run.file_type === 'news'
            ? 'news'
            : 'document',
      )
      setBrief(data.brief)
      setLanguage(data.workspace.language)
      setFormats(data.workspace.content_types)
      setPlatforms(data.workspace.platforms)
      setCombined(data.combined)
      const canReview =
        !!data.combined &&
        !!data.preview &&
        data.info.status !== 'preferences_changed' &&
        data.combined.output_language === data.workspace.language &&
        data.preview.language === data.workspace.language &&
        data.workspace.platforms.every((platform) =>
          data.preview!.items.some((post) => post.platform === platform),
        )
      setPreview(
        canReview
          ? {
              ...data.preview!,
              content_types: data.workspace.content_types,
              platforms: data.workspace.platforms,
              items: data.preview!.items.filter((item) =>
                data.workspace.platforms.includes(item.platform),
              ),
            }
          : null,
      )
      setAssetPack(data.assets)
      setAssetError(data.assets?.image_error || '')
      setVideoStatus(data.video_status)
      setVideoUploads(data.video_uploads)
      setMediaPreferences(readMediaPreferences(id))
      setPreviewError('')
      setProcessingError('')
      setProcessing(data.combined ? 'ready' : 'processing')
      setScreen(canReview && data.workspace.platforms.length > 0 ? 'preview' : 'formats')
      localStorage.setItem('ud-pr-active-run', id)
      if (!data.combined) void beginProcessing(id).catch(() => {})
    } catch (cause) {
      setWorkspaceError(cause instanceof Error ? cause.message : 'Could not reopen campaign.')
      throw cause
    } finally {
      setRestoring(false)
    }
  }

  async function updateBrief(next: CampaignBrief) {
    if (document) await saveBrief(document.run_id, next)
    setBrief(next)
    setPreview(null)
    setPreviewError('')
    setScreen('formats')
  }

  useEffect(() => {
    if (!document || !formats.includes('video')) return
    let alive = true
    void Promise.all([getVideoStatus(document.run_id), listVideoUploads(document.run_id)])
      .then(([status, uploads]) => {
        if (alive && activeRun.current === document.run_id) {
          setVideoStatus(status)
          setVideoUploads(uploads)
        }
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [document, formats])

  useEffect(() => {
    if (
      !document ||
      !formats.includes('video') ||
      !videoStatus ||
      !['planning', 'narration', 'generating_clips', 'composing'].includes(videoStatus.stage)
    )
      return
    const timer = window.setInterval(() => {
      void getVideoStatus(document.run_id)
        .then((status) => {
          if (activeRun.current === document.run_id) setVideoStatus(status)
        })
        .catch((cause) => {
          if (activeRun.current === document.run_id)
            setVideoStatus({
              stage: 'failed',
              url: null,
              error: cause instanceof Error ? cause.message : 'Could not check video status.',
            })
        })
    }, 4000)
    return () => window.clearInterval(timer)
  }, [document, formats, videoStatus?.stage])

  function beginProcessing(runId: string, cached = false): Promise<CombinedResult> {
    if (processingRequest.current?.runId === runId) return processingRequest.current.promise
    setProcessing('processing')
    setProcessingError('')
    const promise = cached
      ? loadSaved(runId).catch(() => processDocument(runId))
      : processDocument(runId)
    processingRequest.current = { runId, promise }
    promise
      .then((result) => {
        if (activeRun.current !== runId) return
        combinedResult.current = result
        setCombined(result)
        if (cached) setLanguage(result.output_language || 'en')
        setProcessing('ready')
      })
      .catch((cause) => {
        if (activeRun.current !== runId) return
        setProcessing('failed')
        setProcessingError(cause instanceof Error ? cause.message : 'Document analysis failed.')
      })
      .finally(() => {
        if (processingRequest.current?.promise === promise) processingRequest.current = null
      })
    return promise
  }

  function handleUploaded(uploaded: UploadResult) {
    activeRun.current = uploaded.run_id
    combinedResult.current = null
    processingRequest.current = null
    setDocument(uploaded)
    setSourceMode(uploaded.file_type === 'news' ? 'news' : 'document')
    setBrief(defaultBrief)
    setWorkspaceError('')
    localStorage.setItem('ud-pr-active-run', uploaded.run_id)
    void reopenCampaign(uploaded.run_id)
      .then((data) => {
        if (activeRun.current === uploaded.run_id) setBrief(data.brief)
      })
      .catch(() => {})
    setLanguage('en')
    setFormats(uploaded.file_type === 'news' ? ['text'] : [])
    setPlatforms(uploaded.file_type === 'news' ? ['website', 'facebook'] : [])
    setCombined(null)
    setPreview(null)
    setAssetPack(null)
    setAssetError('')
    setVideoStatus(null)
    setVideoUploads([])
    setMediaPreferences(readMediaPreferences(uploaded.run_id))
    setPreviewError('')
    videoRetryForce.current = false
    setScreen('formats')
    void beginProcessing(uploaded.run_id, uploaded.cached).catch(() => {})
  }

  function newDocument() {
    localStorage.removeItem('ud-pr-active-run')
    setBrief(defaultBrief)
    setWorkspaceError('')
    activeRun.current = null
    processingRequest.current = null
    combinedResult.current = null
    generating.current = null
    setDocument(null)
    setLanguage('en')
    setCombined(null)
    setPreview(null)
    setAssetPack(null)
    setAssetError('')
    setVideoStatus(null)
    setVideoUploads([])
    setMediaPreferences(emptyMediaPreferences)
    setPreviewError('')
    videoRetryForce.current = false
    setFormats(sourceMode === 'quick' ? ['text'] : [])
    setPlatforms(sourceMode === 'quick' ? ['website', 'facebook'] : [])
    setScreen('upload')
  }

  function changeSourceMode(mode: 'document' | 'quick' | 'news') {
    if (mode === sourceMode) return
    newDocument()
    setSourceMode(mode)
    setFormats(mode === 'quick' ? ['text'] : [])
    setPlatforms(mode === 'quick' ? ['website', 'facebook'] : [])
  }

  async function generateQuick(sentence: string) {
    quickSentence.current = sentence
    activeRun.current = null
    processingRequest.current = null
    combinedResult.current = null
    setDocument(null)
    setCombined(null)
    setPreview(null)
    setAssetPack(null)
    setAssetError('')
    setPreviewError('')
    setProcessingError('')
    setProcessing('processing')
    setScreen('preview')
    const requestedRunId = crypto.randomUUID()
    setQuickStage('researching_announcement')
    const timer = window.setInterval(() => {
      void quickAnnouncementStatus(requestedRunId)
        .then((status) => setQuickStage(status.stage))
        .catch(() => {})
    }, 1000)
    try {
      const result = await createQuickAnnouncement(
        sentence,
        requestedRunId,
        formats.includes('image'),
        language,
        brief,
      )
      const run: UploadResult = {
        run_id: result.run_id,
        filename: 'Quick announcement',
        file_type: 'announcement',
        page_count: null,
        status: 'ready',
        cached: true,
      }
      activeRun.current = run.run_id
      combinedResult.current = result.combined
      setDocument(run)
      localStorage.setItem('ud-pr-active-run', run.run_id)
      setCombined(result.combined)
      setProcessing('ready')
      void createPreviews(run)
    } catch (cause) {
      setProcessing('failed')
      setProcessingError(
        cause instanceof Error ? cause.message : 'Could not prepare the announcement.',
      )
    } finally {
      window.clearInterval(timer)
    }
  }

  function retryAnalysis() {
    if (document) void beginProcessing(document.run_id).catch(() => {})
  }

  function toggleFormat(format: ContentType) {
    if (sourceMode === 'quick' && format === 'text') return
    const next = formats.includes(format)
      ? formats.filter((item) => item !== format)
      : [...formats, format]
    setFormats(next)
    setPlatforms((current) =>
      current.filter(
        (platform) => platformAvailability(platform, next, sourceMode === 'quick').enabled,
      ),
    )
    setPreview(null)
    setAssetPack(null)
    setAssetError('')
    setPreviewError('')
    setScreen('formats')
  }

  function togglePlatform(platform: PlatformName) {
    const next = platforms.includes(platform)
      ? platforms.filter((item) => item !== platform)
      : platformOrder.filter((item) => item === platform || platforms.includes(item))
    setPlatforms(next)
    setPreview(null)
    setAssetPack(null)
    setAssetError('')
    setPreviewError('')
    setScreen('formats')
  }

  function changeLanguage(next: OutputLanguage) {
    if (next === language) return
    setLanguage(next)
    setPreview(null)
    setVideoStatus(null)
    setPreviewError('')
    setScreen('formats')
  }

  async function createPreviews(uploaded: UploadResult) {
    if (generating.current === uploaded.run_id) return
    generating.current = uploaded.run_id
    setPreviewError('')
    try {
      let source = combinedResult.current
      if (!source) {
        const existing =
          processingRequest.current?.runId === uploaded.run_id
            ? processingRequest.current.promise
            : null
        const pending = existing
        if (!pending)
          throw new Error(processingError || 'Source analysis failed. Retry analysis to continue.')
        source = await pending
      }
      if (activeRun.current !== uploaded.run_id) return
      setCombined(source)
      const started = performance.now()
      const textStarted = performance.now()
      const textTask = generatePlatforms(uploaded.run_id, formats, platforms, language)
        .then(async (result) => {
          const latest = await loadSaved(uploaded.run_id)
          if (activeRun.current === uploaded.run_id) {
            combinedResult.current = latest
            setCombined(latest)
            setPreview(result)
            if (
              formats.includes('video') &&
              !formats.includes('image') &&
              !(videoStatus?.stage === 'ready' && videoStatus.url)
            )
              void generateVideo(uploaded.run_id)
          }
          return result
        })
        .finally(() =>
          console.info(`Platform text: ${((performance.now() - textStarted) / 1000).toFixed(1)}s`),
        )
      const imageTask = formats.includes('image')
        ? (() => {
            if (assetPack?.assets.length && !assetPack.image_error && !assetError)
              return Promise.resolve(assetPack)
            const imageStarted = performance.now()
            return generateAssets(uploaded.run_id, platforms).finally(() =>
              console.info(
                `AI image / asset pack: ${((performance.now() - imageStarted) / 1000).toFixed(1)}s`,
              ),
            )
          })()
        : null
      const [textOutcome, imageOutcome] = await Promise.allSettled([textTask, imageTask])
      console.info(`Generate waiting time: ${((performance.now() - started) / 1000).toFixed(1)}s`)
      if (activeRun.current !== uploaded.run_id) return
      if (imageOutcome.status === 'fulfilled' && imageOutcome.value) {
        setAssetPack(imageOutcome.value)
        setAssetError(
          imageOutcome.value.image_error ||
            (imageOutcome.value.assets.length ? '' : 'Visual assets could not be prepared.'),
        )
      } else if (imageOutcome.status === 'rejected') {
        setAssetError(
          imageOutcome.reason instanceof Error
            ? imageOutcome.reason.message
            : 'Visual assets could not be prepared.',
        )
      }
      if (textOutcome.status === 'rejected') throw textOutcome.reason
      if (source.output_language !== language) {
        const translated = await loadSaved(uploaded.run_id)
        combinedResult.current = translated
        setCombined(translated)
      }
      setPreview(textOutcome.value)
      if (
        formats.includes('video') &&
        formats.includes('image') &&
        imageOutcome.status === 'fulfilled' &&
        imageOutcome.value?.assets.length &&
        !(videoStatus?.stage === 'ready' && videoStatus.url)
      )
        void generateVideo(uploaded.run_id)
    } catch (cause) {
      if (activeRun.current !== uploaded.run_id) return
      setRetryStage(combinedResult.current ? 'platform' : 'analysis')
      setPreviewError(
        cause instanceof Error ? cause.message : 'Could not create the platform previews.',
      )
    } finally {
      if (generating.current === uploaded.run_id) generating.current = null
    }
  }

  function handleGenerate() {
    if (!document || platforms.length === 0) return
    setScreen('preview')
    if (formats.includes('video') && videoStatus?.stage === 'failed') setVideoStatus(null)
    if (
      preview &&
      preview.language === language &&
      (!formats.includes('image') ||
        (assetPack?.assets.length && !assetPack.image_error && !assetError)) &&
      preview.content_types.join() === formats.join() &&
      preview.platforms.join() === platforms.join()
    ) {
      if (formats.includes('video')) void generateVideo(document.run_id)
      return
    }
    void createPreviews(document)
  }

  function retryPreview() {
    if (sourceMode === 'quick' && !document) {
      void generateQuick(quickSentence.current)
      return
    }
    if (!document) return
    if (progress.source === 'failed') {
      setPreviewError('')
      void beginProcessing(document.run_id)
        .then(() => createPreviews(document))
        .catch(() => {})
    } else if (progress.platform === 'failed') {
      setPreviewError('')
      void createPreviews(document)
    } else if (progress.image === 'failed') {
      setAssetError('')
      setAssetPack(null)
      void generateAssets(document.run_id, platforms)
        .then((pack) => {
          if (activeRun.current === document.run_id) {
            setAssetPack(pack)
            setAssetError(
              pack.image_error ||
                (pack.assets.length ? '' : 'Visual assets could not be prepared.'),
            )
            if (
              formats.includes('video') &&
              pack.assets.length &&
              !pack.image_error &&
              videoStatus?.stage !== 'ready'
            )
              void generateVideo(document.run_id)
          }
        })
        .catch((cause) => {
          if (activeRun.current === document.run_id)
            setAssetError(
              cause instanceof Error ? cause.message : 'Visual assets could not be prepared.',
            )
        })
    } else if (progress.video === 'failed') {
      setVideoStatus(null)
      void generateVideo(document.run_id, videoRetryForce.current)
    }
  }

  async function savePreview(next: PlatformResult): Promise<PlatformResult> {
    if (!document) throw new Error('Document run is missing.')
    const saved = await savePlatforms(document.run_id, next)
    if (activeRun.current === document.run_id) setPreview(saved)
    return saved
  }

  async function saveMasterDraft(content: MasterContent): Promise<void> {
    if (!document || !combined) throw new Error('Document run is missing.')
    const saved = await saveMaster(document.run_id, content)
    if (activeRun.current === document.run_id) {
      const next = { ...combined, content: saved }
      combinedResult.current = next
      setCombined(next)
    }
  }

  async function regeneratePreview(platform: PlatformName): Promise<void> {
    if (!document || !preview) return
    const result = await regeneratePlatform(document.run_id, formats, platform, language)
    if (activeRun.current === document.run_id) {
      const updated = result.items[0]
      setPreview((current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) => (item.platform === platform ? updated : item)),
            }
          : current,
      )
    }
  }

  async function chooseMain(assetId: string) {
    if (!document) return
    const pack = await setMainAsset(document.run_id, assetId)
    if (activeRun.current === document.run_id) setAssetPack(pack)
  }

  function saveMediaPreferences(runId: string, next: MediaPreferences) {
    localStorage.setItem(`ud-pr-media:${runId}`, JSON.stringify(next))
    if (activeRun.current === runId) setMediaPreferences(next)
  }

  async function choosePrimaryMedia(item: MediaAsset) {
    if (!document) return
    if (item.media_type === 'image') await chooseMain(item.id)
    saveMediaPreferences(document.run_id, { ...mediaPreferences, primaryId: item.id })
  }

  async function removeMedia(item: MediaAsset, nextPrimaryId: string | null) {
    if (!document) return
    if (item.asset_type === 'generated_video') {
      saveMediaPreferences(document.run_id, {
        ...mediaPreferences,
        hideGeneratedVideo: true,
        primaryId: item.primary ? nextPrimaryId : mediaPreferences.primaryId,
      })
      return
    }
    if (item.asset_type === 'uploaded_video')
      await removeVideo(item.id.slice('uploaded_video:'.length))
    else await removeImage(item.id)
    if (item.primary)
      saveMediaPreferences(document.run_id, { ...mediaPreferences, primaryId: nextPrimaryId })
  }

  function restoreGeneratedVideo() {
    if (document)
      saveMediaPreferences(document.run_id, { ...mediaPreferences, hideGeneratedVideo: false })
  }

  async function retryImage() {
    if (!document) return
    const pack = await regenerateImage(document.run_id)
    if (activeRun.current === document.run_id) {
      setAssetPack(pack)
      setAssetError('')
    }
  }

  async function addImages(files: File[]) {
    if (!document) return
    for (const file of files) {
      const pack = await uploadImage(document.run_id, file)
      if (activeRun.current !== document.run_id) return
      setAssetPack(pack)
    }
  }

  async function removeImage(assetId: string) {
    if (!document) return
    const pack = await deleteAsset(document.run_id, assetId)
    if (activeRun.current === document.run_id) setAssetPack(pack)
  }

  async function generateVideo(runId: string, force = false) {
    videoRetryForce.current = force
    if (force && activeRun.current === runId) setVideoStatus(null)
    try {
      const status = await (force ? regenerateVideo(runId) : startVideo(runId))
      if (activeRun.current === runId) setVideoStatus(status)
    } catch (cause) {
      if (activeRun.current === runId)
        setVideoStatus({
          stage: 'failed',
          url: null,
          error: cause instanceof Error ? cause.message : 'Could not start video generation.',
        })
    }
  }

  async function addVideo(file: File) {
    if (!document) return
    const item = await uploadVideo(document.run_id, file)
    if (activeRun.current === document.run_id) setVideoUploads((current) => [...current, item])
  }

  async function removeVideo(id: string) {
    if (!document) return
    const remaining = await deleteVideo(document.run_id, id)
    if (activeRun.current === document.run_id) setVideoUploads(remaining)
  }

  const platformReady =
    !!preview &&
    preview.language === language &&
    preview.content_types.join() === formats.join() &&
    preview.platforms.join() === platforms.join()
  const progress: PackageProgress = {
    source: combined ? 'ready' : processing === 'failed' ? 'failed' : 'pending',
    platform: platformReady
      ? 'ready'
      : previewError && retryStage === 'platform'
        ? 'failed'
        : 'pending',
    image:
      assetError || assetPack?.image_error
        ? 'failed'
        : assetPack?.assets.length
          ? 'ready'
          : 'pending',
    video:
      videoStatus?.stage === 'failed'
        ? 'failed'
        : videoStatus?.stage === 'ready' && videoStatus.url
          ? 'ready'
          : 'pending',
  }
  const packageResult = packageState(formats, progress)
  const previewState = platformReady && combined ? 'ready' : packageResult
  const failedStage =
    progress.source === 'failed'
      ? 'analysis'
      : progress.platform === 'failed'
        ? 'platform'
        : progress.image === 'failed'
          ? 'image'
          : 'video'
  const errorMessage =
    failedStage === 'analysis'
      ? processingError || previewError || 'Source analysis failed.'
      : failedStage === 'platform'
        ? previewError || 'Platform content failed.'
        : failedStage === 'image'
          ? assetError || assetPack?.image_error || 'Visual generation failed.'
          : videoStatus?.error || 'Video generation failed.'
  const retryLabel =
    failedStage === 'analysis'
      ? 'Retry analysis'
      : failedStage === 'platform'
        ? 'Retry platform content'
        : failedStage === 'image'
          ? 'Retry visuals'
          : 'Retry video'

  return (
    <StudioWorkspace
      brief={brief}
      onSaveBrief={updateBrief}
      onOpenCampaign={openCampaign}
      workspaceError={workspaceError}
      restoring={restoring}
      sourceMode={sourceMode}
      quickStage={quickStage}
      language={language}
      onLanguageChange={changeLanguage}
      onSourceModeChange={changeSourceMode}
      onGenerateQuick={generateQuick}
      screen={screen}
      document={document}
      formats={formats}
      platforms={platforms}
      processing={processing}
      processingError={processingError}
      combined={combined}
      preview={preview}
      previewState={previewState}
      progress={progress}
      errorMessage={errorMessage}
      retryLabel={retryLabel}
      assets={assetPack}
      assetError={assetError}
      videoStatus={videoStatus}
      videoUploads={videoUploads}
      mediaPreferences={mediaPreferences}
      onUploaded={handleUploaded}
      onNewDocument={newDocument}
      onRetryAnalysis={retryAnalysis}
      onToggleFormat={toggleFormat}
      onTogglePlatform={togglePlatform}
      onGenerate={handleGenerate}
      onRetryPreview={retryPreview}
      onSave={savePreview}
      onSaveMaster={saveMasterDraft}
      onRegeneratePlatform={regeneratePreview}
      onChoosePrimaryMedia={choosePrimaryMedia}
      onRemoveMedia={removeMedia}
      onRestoreGeneratedVideo={restoreGeneratedVideo}
      onRetryImage={retryImage}
      onAddImages={addImages}
      onRegenerateVideo={() => {
        if (document) void generateVideo(document.run_id, true)
      }}
      onAddVideo={addVideo}
      onDeleteVideo={removeVideo}
    />
  )
}
