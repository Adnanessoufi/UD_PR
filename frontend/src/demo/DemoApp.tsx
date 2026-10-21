import { useEffect, useRef, useState } from 'react'
import { channels, sampleDraft, samples, type Channel, type Draft, type Language } from './samples'
import './demo.css'

const repo = 'https://github.com/Adnanessoufi/UD_PR'
type View = 'drafts' | 'media' | 'source' | 'questions'

function downloadText(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <span aria-hidden="true">{diagonal ? '↗' : '→'}</span>
}

export default function DemoApp() {
  const [sampleId, setSampleId] = useState('research')
  const [language, setLanguage] = useState<Language>('en')
  const [channel, setChannel] = useState<Channel>('website')
  const [view, setView] = useState<View>('drafts')
  const [edits, setEdits] = useState<Record<string, Draft>>({})
  const [editing, setEditing] = useState(false)
  const [factIndex, setFactIndex] = useState(0)
  const [questionIndex, setQuestionIndex] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const previewRef = useRef<HTMLDivElement>(null)
  const sample = samples.find((item) => item.id === sampleId) || samples[0]
  const text = sample[language]
  const editKey = `${sample.id}:${language}:${channel}`
  const draft = edits[editKey] || sampleDraft(sample, language, channel)
  const changed = Boolean(edits[editKey])
  const activeChannel = channels.find((item) => item.id === channel)!
  const selectedFact = text.facts[factIndex]
  const selectedQuestion = questionIndex === null ? null : text.questions[questionIndex]
  const answerFact = text.facts.find((item) => item.id === selectedQuestion?.factId)

  useEffect(() => {
    document.title = 'UD PR Studio | Explore the demo'
    return () => {
      document.title = 'UD PR Studio'
    }
  }, [])
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 5000)
    return () => window.clearTimeout(timer)
  }, [notice])

  function chooseSample(id: string) {
    setSampleId(id)
    setFactIndex(0)
    setQuestionIndex(null)
    setEditing(false)
    setNotice('')
  }
  function chooseLanguage(value: Language) {
    setLanguage(value)
    setEditing(false)
    setQuestionIndex(null)
    setNotice('')
  }
  function resetDemo() {
    setEdits({})
    setEditing(false)
    setSampleId('research')
    setLanguage('en')
    setChannel('website')
    setView('drafts')
    setFactIndex(0)
    setQuestionIndex(null)
    setNotice('Back to the original samples. Your edits have been cleared.')
  }
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setNotice('Copied. You can paste it wherever you need it.')
    } catch {
      setNotice('Copy is unavailable in this browser. Use Download text to save a copy.')
    }
  }
  function exportCampaign() {
    const output = [
      '# UD PR Studio sample campaign',
      'Fictional example. Prepared sample content, not a live AI response or a real study/event.',
      `Language: ${language}`,
      'Local edits have not been verified. Do not use the sample review as approval of edited text.',
      ...channels.map((item) => {
        const current =
          edits[`${sample.id}:${language}:${item.id}`] || sampleDraft(sample, language, item.id)
        return `## ${item.label}\n\n${current.title}\n\n${current.body}`
      }),
      `## Original sample source\n\n${text.source}`,
    ].join('\n\n')
    downloadText(`ud-pr-${sample.id}-${language}.md`, output)
    setNotice('Campaign downloaded, including the sample source and any local edits.')
  }

  return (
    <div className="showcase">
      <a className="showcase-skip" href="#demo-workspace">
        Skip to demo
      </a>
      <header className="showcase-header">
        <a href="#" className="showcase-brand" aria-label="UD PR Studio home">
          <span className="showcase-brand-mark" aria-hidden="true">
            UD<span>✳</span>
          </span>
          <span>
            PR Studio<small>A student project by Adnane Essoufi</small>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <span className="showcase-live">
            <i /> Interactive demo
          </span>
          <a href={repo} target="_blank" rel="noreferrer">
            View the code <Arrow diagonal />
          </a>
        </nav>
      </header>

      <section className="showcase-hero">
        <div>
          <p className="showcase-eyebrow">From the source to the story</p>
          <h1>
            Good research deserves
            <br />a clear explanation<span>.</span>
          </h1>
          <p className="showcase-hero-copy">
            I made this to help turn university papers and announcements into content people can
            actually read. Have a look around.
          </p>
          <a
            className="showcase-hero-cta"
            href="#demo-workspace"
            onClick={() =>
              previewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }
          >
            Explore a sample <Arrow />
          </a>
        </div>
        <div
          className="showcase-hero-visual"
          aria-label="Workflow: one source becomes drafts for different channels, with a source review"
        >
          <div className="showcase-paper-stack">
            <span className="showcase-paper-label">THE ORIGINAL SOURCE</span>
            <div className="showcase-paper-title">
              A quieter place
              <br />
              to study.
            </div>
            <div className="showcase-paper-lines">
              <i />
              <i />
              <i />
            </div>
            <span className="showcase-paper-foot">
              24 volunteers · 4 weeks
              <br />
              Fictional study for this demo
            </span>
          </div>
          <div className="showcase-floating-card">
            <span className="showcase-tick">✓</span>
            <div>
              Keep the facts.<small>Keep the limitations, too.</small>
            </div>
          </div>
          <div className="showcase-channel-strip">
            <span>Article</span>
            <span>Social posts</span>
            <span>Video</span>
          </div>
        </div>
      </section>

      <div className="showcase-method" aria-label="Demo workflow">
        <span>
          <b>01</b> Choose a source
        </span>
        <span>
          <b>02</b> Explore the drafts
        </span>
        <span>
          <b>03</b> Check the evidence
        </span>
        <span>
          <b>04</b> Take a copy
        </span>
      </div>

      <main id="demo-workspace" className="showcase-workspace" ref={previewRef}>
        <div className="showcase-workspace-heading">
          <div>
            <p className="showcase-eyebrow">Try the workflow</p>
            <h2>One source. A few ways to share it.</h2>
          </div>
          <button type="button" className="showcase-text-button" onClick={resetDemo}>
            Reset demo <span aria-hidden="true">↺</span>
          </button>
        </div>
        <div className="showcase-disclosure">
          <span aria-hidden="true">ⓘ</span>
          <p>
            <strong>This is a sample demo.</strong> The study and event are fictional. Drafts,
            answers and review examples are prepared in advance. Your edits stay in this tab. No
            live AI generation or publishing.
          </p>
        </div>

        <div className="showcase-grid">
          <aside className="showcase-sidebar" aria-label="Sample and language selection">
            <p className="showcase-sidebar-label">PICK A SAMPLE</p>
            {samples.map((item, index) => (
              <button
                type="button"
                key={item.id}
                className={`showcase-sample ${sample.id === item.id ? 'is-active' : ''}`}
                aria-pressed={sample.id === item.id}
                onClick={() => chooseSample(item.id)}
              >
                <span className="showcase-sample-number">0{index + 1}</span>
                <span>
                  <small>{item.kind}</small>
                  <strong>{item.label}</strong>
                  <em>
                    {item.id === 'research'
                      ? 'A small pilot with clear limits'
                      : 'A brief with the details that matter'}
                  </em>
                </span>
                <span aria-hidden="true">↗</span>
              </button>
            ))}
            <div className="showcase-language">
              <p className="showcase-sidebar-label">DRAFT LANGUAGE</p>
              <div role="group" aria-label="Draft language">
                <button
                  type="button"
                  aria-pressed={language === 'en'}
                  onClick={() => chooseLanguage('en')}
                >
                  English
                </button>
                <button
                  type="button"
                  aria-pressed={language === 'hu'}
                  onClick={() => chooseLanguage('hu')}
                >
                  Magyar
                </button>
              </div>
              <p>The sample source and drafts are available in both languages.</p>
            </div>
            <div className="showcase-source-card">
              <span aria-hidden="true">▤</span>
              <small>YOUR SAMPLE SOURCE</small>
              <strong>{text.sourceTitle}</strong>
              <button
                type="button"
                onClick={() => {
                  setView('source')
                  setEditing(false)
                }}
              >
                Read the source <Arrow />
              </button>
            </div>
            <a
              className="showcase-local-link"
              href={`${repo}#try-it-locally`}
              target="_blank"
              rel="noreferrer"
            >
              Want to use your own document?
              <br />
              <strong>
                Run the full app locally <Arrow diagonal />
              </strong>
            </a>
          </aside>

          <section className="showcase-editor" aria-label="Campaign sample">
            <div className="showcase-editor-top">
              <div>
                <span className="showcase-eyebrow">{sample.kind}</span>
                <h3>{text.title}</h3>
                <p>{text.summary}</p>
              </div>
              <span className="showcase-sample-badge">SAMPLE</span>
            </div>
            <div className="showcase-tabs" role="tablist" aria-label="Explore campaign">
              {(
                [
                  ['drafts', 'Drafts'],
                  ['media', 'Images & video'],
                  ['source', 'Source & review'],
                  ['questions', 'Ask the story'],
                ] as [View, string][]
              ).map(([id, label]) => (
                <button
                  type="button"
                  role="tab"
                  id={`tab-${id}`}
                  aria-selected={view === id}
                  aria-controls="demo-panel"
                  key={id}
                  onClick={() => {
                    setView(id)
                    setEditing(false)
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <div id="demo-panel" role="tabpanel" aria-labelledby={`tab-${view}`} tabIndex={0}>
              {view === 'drafts' && (
                <>
                  <div className="showcase-channels" role="group" aria-label="Preview channel">
                    {channels.map((item) => (
                      <button
                        type="button"
                        key={item.id}
                        aria-pressed={channel === item.id}
                        onClick={() => {
                          setChannel(item.id)
                          setEditing(false)
                          setNotice('')
                        }}
                      >
                        <span aria-hidden="true">{item.mark}</span>
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <div className="showcase-preview-label">
                    <span>
                      {activeChannel.label} preview · {language === 'en' ? 'English' : 'Magyar'}
                    </span>
                    <button type="button" onClick={() => setEditing(!editing)}>
                      {editing ? 'Done editing' : 'Try editing'}
                    </button>
                  </div>
                  <article
                    className={`showcase-draft ${channel === 'website' ? 'is-article' : 'is-social'}`}
                    lang={language}
                  >
                    {channel === 'website' ? (
                      <div className="showcase-article-masthead">
                        <span>THE CAMPUS NOTE</span>
                        <small>Fictional university news</small>
                      </div>
                    ) : (
                      <div className="showcase-social-masthead">
                        <span className="showcase-avatar">UD</span>
                        <div>
                          <strong>Sample campus account</strong>
                          <small>{activeChannel.label} · Prepared example</small>
                        </div>
                      </div>
                    )}
                    {editing ? (
                      <div className="showcase-edit-fields">
                        <label>
                          Headline
                          <input
                            maxLength={300}
                            value={draft.title}
                            onChange={(event) =>
                              setEdits({
                                ...edits,
                                [editKey]: { ...draft, title: event.target.value },
                              })
                            }
                          />
                        </label>
                        <label>
                          Draft text
                          <textarea
                            rows={12}
                            maxLength={10000}
                            value={draft.body}
                            onChange={(event) =>
                              setEdits({
                                ...edits,
                                [editKey]: { ...draft, body: event.target.value },
                              })
                            }
                          />
                        </label>
                        <small>
                          Edits are local to this tab. They haven't been checked against the source.
                        </small>
                      </div>
                    ) : (
                      <>
                        <h2>{draft.title}</h2>
                        <div className="showcase-draft-body">
                          {draft.body.split('\n\n').map((paragraph, index) => (
                            <p key={index}>{paragraph}</p>
                          ))}
                        </div>
                      </>
                    )}
                    {channel !== 'website' && (
                      <img
                        className="showcase-social-image"
                        src={sample.image}
                        alt={`Illustrative poster for ${sample.label}. Fictional sample.`}
                      />
                    )}
                    <div className="showcase-draft-foot">
                      <span>
                        {changed
                          ? 'Local edit · needs a new review'
                          : 'Prepared draft · fictional source'}
                      </span>
                      <span>{language.toUpperCase()}</span>
                    </div>
                  </article>
                  {changed && (
                    <div className="showcase-edit-warning" role="status">
                      You changed this draft. The sample review no longer applies to it.{' '}
                      <button
                        type="button"
                        onClick={() => {
                          const next = { ...edits }
                          delete next[editKey]
                          setEdits(next)
                          setEditing(false)
                        }}
                      >
                        Restore original
                      </button>
                    </div>
                  )}
                  <div className="showcase-draft-actions">
                    <button
                      className="showcase-primary"
                      type="button"
                      onClick={() => void copy(`${draft.title}\n\n${draft.body}`)}
                    >
                      Copy this draft <span aria-hidden="true">⧉</span>
                    </button>
                    <button
                      className="showcase-secondary"
                      type="button"
                      onClick={() =>
                        downloadText(
                          `${sample.id}-${channel}-${language}.txt`,
                          `FICTIONAL SAMPLE. ${changed ? 'Local edits have not been verified.' : 'Prepared draft.'}\n\n${draft.title}\n\n${draft.body}`,
                        )
                      }
                    >
                      Download text <span aria-hidden="true">↓</span>
                    </button>
                  </div>
                </>
              )}

              {view === 'media' && (
                <div className="showcase-media-panel">
                  <p className="showcase-section-note">
                    Prepared examples of the media a campaign can include. The poster is
                    illustrative; the short sample video has English narration and captions.
                  </p>
                  <h4>Campaign image</h4>
                  <img
                    className="showcase-poster"
                    src={sample.image}
                    alt={`Sample poster: ${sample.label}. Fictional example.`}
                  />
                  <a className="showcase-download-link" href={sample.image} download>
                    Download sample image <span aria-hidden="true">↓</span>
                  </a>
                  <h4>
                    Sample video <small>English narration · captions included</small>
                  </h4>
                  <video
                    key={sample.id}
                    className="showcase-video"
                    controls
                    playsInline
                    preload="metadata"
                    poster={sample.image}
                    aria-label={`English sample video for ${sample.label}`}
                  >
                    <source src={sample.video} type="video/mp4" />
                    <track
                      kind="captions"
                      src={`/demo/${sample.id}.vtt`}
                      srcLang="en"
                      label="English"
                      default
                    />
                    Your browser does not support video playback.
                  </video>
                  <a className="showcase-download-link" href={sample.video} download>
                    Download sample video <span aria-hidden="true">↓</span>
                  </a>
                </div>
              )}

              {view === 'source' && (
                <div className="showcase-source-panel">
                  <div className="showcase-section-title">
                    <div>
                      <h4>Start with what the source says.</h4>
                      <p>
                        This review was prepared for the original sample drafts. It isn't a live
                        checker result or an approval.
                      </p>
                    </div>
                    <span className="showcase-example-tag">Example review</span>
                  </div>
                  <div className="showcase-fact-list" role="group" aria-label="Source claims">
                    {text.facts.map((fact, index) => (
                      <button
                        type="button"
                        aria-pressed={factIndex === index}
                        key={fact.id}
                        onClick={() => setFactIndex(index)}
                      >
                        <span>{fact.id}</span>
                        <strong>{fact.claim}</strong>
                        <span aria-hidden="true">↗</span>
                      </button>
                    ))}
                  </div>
                  <div className="showcase-evidence" lang={language}>
                    <span className="showcase-evidence-label">
                      EXCERPT FROM THE FICTIONAL SOURCE
                    </span>
                    <blockquote>{selectedFact.excerpt}</blockquote>
                    <p>
                      <span aria-hidden="true">✓</span> {selectedFact.note}
                    </p>
                  </div>
                  <details className="showcase-full-source">
                    <summary>Read the full sample source</summary>
                    <pre lang={language}>{text.source}</pre>
                  </details>
                  <button
                    type="button"
                    className="showcase-secondary"
                    onClick={() => downloadText(`${sample.id}-source-${language}.txt`, text.source)}
                  >
                    Download sample source <span aria-hidden="true">↓</span>
                  </button>
                  <div className="showcase-review-note">
                    <strong>What happens in the full app?</strong>
                    <p>
                      A separate model checks the draft against the source. You inspect the
                      evidence, review the media and approve that version. Editing it means checking
                      and approving again.
                    </p>
                  </div>
                </div>
              )}

              {view === 'questions' && (
                <div className="showcase-questions-panel">
                  <p className="showcase-eyebrow">Living Stories</p>
                  <h4>What would you ask about this?</h4>
                  <p className="showcase-section-note">
                    Try a prepared question to see how an answer connects to the source. These are
                    saved examples, not live AI responses.
                  </p>
                  <div className="showcase-question-list" lang={language}>
                    {text.questions.map((question, index) => (
                      <button
                        type="button"
                        aria-pressed={questionIndex === index}
                        key={question.question}
                        onClick={() => setQuestionIndex(index)}
                      >
                        {question.question}
                        <Arrow />
                      </button>
                    ))}
                  </div>
                  {selectedQuestion && answerFact ? (
                    <div className="showcase-answer" lang={language}>
                      <span className="showcase-evidence-label">PREPARED SAMPLE ANSWER</span>
                      <p>{selectedQuestion.answer}</p>
                      <div className="showcase-answer-evidence">
                        <span>{answerFact.id} · Source excerpt</span>
                        <blockquote>{answerFact.excerpt}</blockquote>
                      </div>
                      <button
                        className="showcase-secondary"
                        type="button"
                        onClick={() => void copy(selectedQuestion.answer)}
                      >
                        Copy sample reply <span aria-hidden="true">⧉</span>
                      </button>
                    </div>
                  ) : (
                    <div className="showcase-answer-empty">
                      <span aria-hidden="true">“</span>
                      <p>Pick a question. The answer and its source excerpt will appear here.</p>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="showcase-export-bar">
              <div>
                <strong>Keep a copy of the campaign.</strong>
                <span>All six channel drafts, plus the sample source.</span>
              </div>
              <button type="button" onClick={exportCampaign}>
                Download campaign <span aria-hidden="true">↓</span>
              </button>
            </div>
          </section>
        </div>
        <div className="showcase-notice" role="status" aria-live="polite">
          {notice}
        </div>
      </main>

      <section className="showcase-about">
        <div>
          <p className="showcase-eyebrow">Behind the demo</p>
          <h2>The full app goes further.</h2>
          <p>
            Upload your own documents, generate drafts and media, then check the claims before
            publishing. The code and local setup are on GitHub.
          </p>
          <a href={repo} target="_blank" rel="noreferrer">
            See how I built it <Arrow diagonal />
          </a>
        </div>
        <dl>
          <div>
            <dt>React + TypeScript</dt>
            <dd>The workspace and channel previews</dd>
          </div>
          <div>
            <dt>Python + FastAPI</dt>
            <dd>Document processing and saved campaigns</dd>
          </div>
          <div>
            <dt>OpenAI + ElevenLabs</dt>
            <dd>Content, source checks and voice in the full app</dd>
          </div>
        </dl>
      </section>
      <footer className="showcase-footer">
        <span>
          UD PR Studio <span aria-hidden="true">·</span> Built by Adnane Essoufi
        </span>
        <span>Student project. Not an official university service.</span>
        <a
          href="https://www.linkedin.com/in/adnane-essoufi-78b7b025b/"
          target="_blank"
          rel="noreferrer"
        >
          Say hello <Arrow diagonal />
        </a>
      </footer>
    </div>
  )
}
