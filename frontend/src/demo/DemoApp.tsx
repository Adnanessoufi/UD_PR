import { useEffect, useState } from 'react'
import StudioWorkspace from '../components/StudioWorkspace'
import StoryRoom from '../components/StoryRoom'
import { defaultBrief, type CampaignBrief } from '../types/campaign'
import type { CombinedResult, MasterContent } from '../types/content'
import {
  platformAvailability,
  type ContentType,
  type PlatformName,
  type PlatformResult,
} from '../types/platform'
import type { AssetPack } from '../types/assets'
import { channels, sampleDraft, samples, type Language, type Sample } from './samples'
import './demo.css'

function download(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function combinedSample(sample: Sample, language: Language): CombinedResult {
  const text = sample[language]
  return {
    output_language: language,
    analysis: {
      document_type: 'sample_document',
      source_language: language,
      title: text.sourceTitle,
      organization: 'Fictional sample',
      people: [],
      summary: text.summary,
      key_facts: text.facts.map((fact) => ({
        id: fact.id,
        statement: fact.claim,
        category: 'sample',
        page: null,
        source_excerpt: fact.excerpt,
        importance: 'high',
      })),
      important_numbers: [],
      important_dates: [],
      conditions_and_limitations: ['Fictional source. Prepared sample content.'],
      communication_focus: text.summary,
      warning: 'Fictional sample. These drafts and source excerpts are prepared in advance.',
    },
    content: {
      headline: text.article.title,
      lead: text.summary,
      body: text.article.body,
      short_summary: text.summary,
      key_messages: text.facts.map((fact) => fact.claim),
      press_release: text.article.body,
      source_fact_ids: text.facts.map((fact) => fact.id),
    },
  }
}

export default function DemoApp() {
  const [sampleId, setSampleId] = useState('research')
  const [language, setLanguage] = useState<Language>('en')
  const [screen, setScreen] = useState<'upload' | 'preview'>('upload')
  const [formats, setFormats] = useState<ContentType[]>(['text', 'image', 'video'])
  const [platforms, setPlatforms] = useState<PlatformName[]>(channels.map((channel) => channel.id))
  const [brief, setBrief] = useState<CampaignBrief>(defaultBrief)
  const [savedPosts, setSavedPosts] = useState<PlatformResult | null>(null)
  const [savedMaster, setSavedMaster] = useState<MasterContent | null>(null)
  const [primaryId, setPrimaryId] = useState<string | null>(null)
  const [hideImage, setHideImage] = useState(false)
  const [hideVideo, setHideVideo] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const sample = samples.find((item) => item.id === sampleId) || samples[0]
  const text = sample[language]
  const original = combinedSample(sample, language)
  const combined = { ...original, content: savedMaster || original.content }
  const edited = Boolean(savedPosts || savedMaster)
  const preview: PlatformResult = savedPosts || {
    language,
    content_types: formats,
    platforms,
    items: platforms.map((platform) => ({
      platform,
      ...sampleDraft(sample, language, platform),
      source_fact_ids: text.facts.map((fact) => fact.id),
    })),
  }
  const assets: AssetPack = {
    document_family: 'research',
    recommended_asset_id: 'sample-image',
    main_asset_id: 'sample-image',
    image_attempted: true,
    image_error: null,
    assets: hideImage
      ? []
      : [
          {
            id: 'sample-image',
            type: 'editorial_visual',
            label: 'Prepared sample image',
            source: 'local',
            path: sample.image,
            recommended: true,
          },
        ],
  }
  const answersFor = (lang: Language) =>
    sample[lang].questions.map((question) => ({
      ...question,
      excerpt: sample[lang].facts.find((fact) => fact.id === question.factId)!.excerpt,
    }))
  const demoAnswers = { en: answersFor('en'), hu: answersFor('hu') }

  useEffect(() => {
    document.title = 'UD PR Studio | Sample demo'
    return () => {
      document.title = 'UD PR Studio'
    }
  }, [])
  useEffect(() => {
    if (!sourceOpen && !libraryOpen) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSourceOpen(false)
        setLibraryOpen(false)
      }
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [sourceOpen, libraryOpen])

  function clearEdits() {
    setSavedPosts(null)
    setSavedMaster(null)
    setPrimaryId(null)
    setHideImage(false)
    setHideVideo(false)
    setNotice('')
  }
  function chooseSample(id: string) {
    setSampleId(id)
    clearEdits()
    setScreen('upload')
    setLibraryOpen(false)
  }
  function chooseLanguage(value: Language) {
    setLanguage(value)
    clearEdits()
  }
  function exportText() {
    download(
      `ud-pr-${sample.id}-${language}.md`,
      [
        '# UD PR Studio sample campaign',
        'Fictional sample. Prepared drafts. Local edits have not been verified.',
        ...preview.items.map(
          (post) => `## ${post.platform.toUpperCase()}\n\n${post.title}\n\n${post.body}`,
        ),
        `## Sample source\n\n${text.source}`,
      ].join('\n\n'),
    )
    setNotice('Sample text downloaded, including your local edits and the source.')
  }
  async function copyText() {
    try {
      await navigator.clipboard.writeText(
        preview.items.map((post) => `${post.title}\n\n${post.body}`).join('\n\n'),
      )
      setNotice('Platform text copied.')
    } catch {
      setNotice('Copy is unavailable. Use Download text package instead.')
    }
  }
  const unavailable = async () => {
    throw new Error(
      'Live generation and uploads are available in the full app. This demo uses prepared samples.',
    )
  }

  return (
    <>
      <StudioWorkspace
        demo={{
          tools: (
            <section className="ud-demo-bar" aria-label="Public sample demo">
              <div>
                <strong>Sample demo</strong>
                <p>
                  Prepared, fictional examples in the studio. No live AI generation or publishing.
                  Your edits stay in this tab.
                </p>
              </div>
              <div className="ud-demo-actions" role="group" aria-label="Sample campaigns">
                <button
                  type="button"
                  className="ud-secondary-button"
                  aria-pressed={sampleId === 'research'}
                  onClick={() => chooseSample('research')}
                >
                  Research sample
                </button>
                <button
                  type="button"
                  className="ud-secondary-button"
                  aria-pressed={sampleId === 'announcement'}
                  onClick={() => chooseSample('announcement')}
                >
                  Announcement sample
                </button>
                <button
                  type="button"
                  className="ud-text-button"
                  onClick={() => setSourceOpen(true)}
                >
                  Read sample source
                </button>
                <a href="https://github.com/Adnanessoufi/UD_PR" target="_blank" rel="noreferrer">
                  GitHub ↗
                </a>
              </div>
              {notice && (
                <p className="ud-source-note" role="status">
                  {notice}
                </p>
              )}
            </section>
          ),
          story: (
            <StoryRoom
              key={`${sample.id}:${language}`}
              runId={`sample-${sample.id}`}
              language={language}
              story={combined.content}
              demoAnswers={demoAnswers}
            />
          ),
          review: (
            <section className="ud-verification" aria-label="Prepared sample review">
              <div className="ud-verification-heading">
                <div>
                  <p className="ud-eyebrow">Validation</p>
                  <h2>Sample source review</h2>
                  <p>
                    Prepared examples of the claims and evidence. This is not a live model check or
                    an approval.
                  </p>
                </div>
              </div>
              {edited && (
                <p className="ud-verification-warning" role="status">
                  You've edited the sample. The prepared review only applies to the original draft.
                  Live checking and approval are available in the full app.
                </p>
              )}
              <div className="ud-demo-evidence">
                {text.facts.map((fact) => (
                  <details key={fact.id}>
                    <summary>
                      {fact.id} · {fact.claim}
                    </summary>
                    <blockquote>{fact.excerpt}</blockquote>
                    <p>{fact.note}</p>
                  </details>
                ))}
              </div>
              <p className="ud-source-note">Publishing is disabled in this public sample demo.</p>
            </section>
          ),
          exports: (
            <section className="workspace-export">
              <div>
                <h2>Take the campaign with you</h2>
                <p>
                  Download your sample drafts or prepared media. Edited text has not been verified.
                </p>
              </div>
              <div className="workspace-inline-actions">
                <button
                  className="ud-secondary-button"
                  type="button"
                  onClick={() => void copyText()}
                >
                  Copy platform text
                </button>
                <button className="ud-secondary-button" type="button" onClick={exportText}>
                  Download text package
                </button>
                <a className="ud-secondary-button" href={sample.image} download>
                  Download sample image
                </a>
                <a className="ud-secondary-button" href={sample.video} download>
                  Download sample video (English)
                </a>
              </div>
            </section>
          ),
          onCampaigns: () => setLibraryOpen(true),
          onChooseSource: () => setLibraryOpen(true),
        }}
        brief={brief}
        onSaveBrief={async (value) => {
          setBrief(value)
          setNotice(
            'Brief saved in this tab. The demo keeps the prepared drafts; live regeneration is available in the full app.',
          )
        }}
        onOpenCampaign={async (id) => chooseSample(id)}
        workspaceError=""
        restoring={false}
        sourceMode="document"
        quickStage="ready"
        onSourceModeChange={(mode) => chooseSample(mode === 'quick' ? 'announcement' : 'research')}
        language={language}
        onLanguageChange={chooseLanguage}
        onGenerateQuick={async () => setScreen('preview')}
        screen={screen}
        document={{
          run_id: `sample-${sample.id}`,
          filename: sample.filename,
          file_type: 'docx',
          page_count: null,
          status: 'ready',
        }}
        formats={formats}
        platforms={platforms}
        processing="ready"
        processingError=""
        combined={combined}
        preview={screen === 'preview' ? preview : null}
        previewState="ready"
        progress={{ source: 'ready', platform: 'ready', image: 'ready', video: 'ready' }}
        errorMessage=""
        retryLabel="Open sample"
        assets={assets}
        assetError=""
        videoStatus={null}
        videoUploads={
          hideVideo
            ? []
            : [
                {
                  id: 'sample-video',
                  filename: sample.video.split('/').pop()!,
                  label: 'Prepared sample video · English narration',
                  duration_seconds: sample.id === 'research' ? 28.5 : 27.6,
                  url: sample.video,
                },
              ]
        }
        mediaPreferences={{ primaryId, hideGeneratedVideo: false }}
        onUploaded={() => undefined}
        onNewDocument={() => {
          clearEdits()
          setScreen('upload')
        }}
        onRetryAnalysis={() => undefined}
        onToggleFormat={(format) => {
          const next = formats.includes(format)
            ? formats.filter((item) => item !== format)
            : [...formats, format]
          setFormats(next)
          setPlatforms((current) =>
            current.filter((platform) => platformAvailability(platform, next).enabled),
          )
          setSavedPosts(null)
        }}
        onTogglePlatform={(platform) => {
          setPlatforms((current) =>
            current.includes(platform)
              ? current.filter((item) => item !== platform)
              : [...current, platform],
          )
          setSavedPosts(null)
        }}
        onGenerate={() => setScreen('preview')}
        onRetryPreview={() => setScreen('preview')}
        onSave={async (value) => {
          setSavedPosts(value)
          return value
        }}
        onSaveMaster={async (value) => setSavedMaster(value)}
        onRegeneratePlatform={unavailable}
        onChoosePrimaryMedia={async (item) => setPrimaryId(item.id)}
        onRemoveMedia={async (item, next) => {
          if (item.media_type === 'image') setHideImage(true)
          else setHideVideo(true)
          setPrimaryId(next)
        }}
        onRestoreGeneratedVideo={() => setHideVideo(false)}
        onRetryImage={unavailable}
        onAddImages={unavailable}
        onRegenerateVideo={() => setNotice('Live video generation is available in the full app.')}
        onAddVideo={unavailable}
        onDeleteVideo={async () => setHideVideo(true)}
      />
      {(libraryOpen || sourceOpen) && (
        <div
          className="workspace-modal"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setLibraryOpen(false)
              setSourceOpen(false)
            }
          }}
        >
          <section
            className="workspace-library"
            role="dialog"
            aria-modal="true"
            aria-labelledby="demo-dialog-title"
          >
            <header>
              <div>
                <p className="ud-eyebrow">Prepared samples</p>
                <h2 id="demo-dialog-title">{sourceOpen ? text.sourceTitle : 'Sample campaigns'}</h2>
              </div>
              <button
                className="ud-secondary-button"
                type="button"
                onClick={() => {
                  setLibraryOpen(false)
                  setSourceOpen(false)
                }}
              >
                Close
              </button>
            </header>
            {sourceOpen ? (
              <div className="ud-demo-source">
                <pre lang={language}>{text.source}</pre>
                <button
                  type="button"
                  className="ud-secondary-button"
                  onClick={() => download(`${sample.id}-source-${language}.txt`, text.source)}
                >
                  Download sample source
                </button>
              </div>
            ) : (
              <div className="ud-demo-campaigns">
                {samples.map((item) => (
                  <button
                    type="button"
                    className="ud-secondary-button"
                    key={item.id}
                    onClick={() => chooseSample(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  )
}
