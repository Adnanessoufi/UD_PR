import { useEffect, useRef, useState } from 'react'
import { approvePackage, checkPackage, getReviewStatus } from '../services/verification'
import type { ClaimReview, ReviewContext, ReviewStatus, Verdict } from '../types/verification'
import './verification.css'

const labels: Record<Verdict, string> = {
  supported: 'Supported',
  exaggerated: 'Exaggerated',
  unsupported: 'Unsupported',
  needs_review: 'Needs review',
  non_factual: 'Non-factual text',
}
const blocking = (claim: ClaimReview) =>
  ['unsupported', 'exaggerated', 'needs_review'].includes(claim.verdict)
type Props = {
  runId: string
  context: ReviewContext
  revisionKey: string
  editing: boolean
  onStatus: (status: ReviewStatus | null) => void
}
export default function VerificationPanel({
  runId,
  context,
  revisionKey,
  editing,
  onStatus,
}: Props) {
  const [status, setStatus] = useState<ReviewStatus | null>(null)
  const [busy, setBusy] = useState<'loading' | 'checking' | 'approving' | null>('loading')
  const [error, setError] = useState('')
  const [attentionOnly, setAttentionOnly] = useState(true)
  const [selected, setSelected] = useState<string | null>(null)
  const [reviewer, setReviewer] = useState('')
  const [claimsReviewed, setClaimsReviewed] = useState(false)
  const [mediaReviewed, setMediaReviewed] = useState(false)
  const [showPage, setShowPage] = useState(false)
  const contextKey = JSON.stringify(context)
  const requestVersion = useRef(0)

  useEffect(() => {
    let alive = true
    ++requestVersion.current
    setStatus(null)
    onStatus(null)
    setError('')
    setBusy('loading')
    setClaimsReviewed(false)
    setMediaReviewed(false)
    setShowPage(false)
    setSelected(null)
    const selection = JSON.parse(contextKey) as ReviewContext
    void getReviewStatus(runId, selection)
      .then(async (current) => {
        if (!alive) return
        if (!current.report && current.checker_ready && !editing) {
          setBusy('checking')
          current = await checkPackage(runId, selection)
        }
        if (alive) {
          setStatus(current)
          onStatus(current)
        }
      })
      .catch((cause) => {
        if (alive)
          setError(cause instanceof Error ? cause.message : 'Could not check this package.')
      })
      .finally(() => {
        if (alive) setBusy(null)
      })
    return () => {
      alive = false
      ++requestVersion.current
    }
    // Context is serialized so media selection and edits trigger a new version check.
  }, [runId, contextKey, revisionKey, editing])

  async function check() {
    const version = ++requestVersion.current
    setBusy('checking')
    setError('')
    setClaimsReviewed(false)
    setMediaReviewed(false)
    onStatus(null)
    try {
      const result = await checkPackage(runId, context, true)
      if (version !== requestVersion.current) return
      setStatus(result)
      onStatus(result)
      setSelected(null)
      setShowPage(false)
    } catch (cause) {
      if (version === requestVersion.current) {
        setError(cause instanceof Error ? cause.message : 'Verification failed.')
        setStatus(null)
      }
    } finally {
      if (version === requestVersion.current) setBusy(null)
    }
  }
  async function approve() {
    if (!status || !claimsReviewed || !mediaReviewed || reviewer.trim().length < 2) return
    const version = ++requestVersion.current
    setBusy('approving')
    setError('')
    try {
      const result = await approvePackage(runId, context, status.version, reviewer.trim())
      if (version !== requestVersion.current) return
      setStatus(result)
      onStatus(result)
    } catch (cause) {
      if (version === requestVersion.current) {
        setError(cause instanceof Error ? cause.message : 'Approval failed.')
        onStatus(null)
      }
    } finally {
      if (version === requestVersion.current) setBusy(null)
    }
  }
  const claims = status?.report?.claims || []
  const filtered = attentionOnly ? claims.filter(blocking) : claims
  const current = filtered.find((claim) => claim.id === selected) || filtered[0]
  const supported = claims.filter((claim) => claim.verdict === 'supported').length
  const firstPdf =
    current?.evidence.findIndex(
      (evidence) => evidence.source_type === 'document' && evidence.page !== null,
    ) ?? -1
  return (
    <section className="ud-verification" aria-label="Validation and human approval">
      <div className="ud-verification-heading">
        <div>
          <p className="ud-eyebrow">Validation</p>
          <h2>Check the claims. Review the evidence.</h2>
          <p>
            A separate model checks the meaning; code confirms quotes and numbers. A person approves
            the final package.
          </p>
        </div>
        <button
          type="button"
          className="ud-secondary-button"
          disabled={!!busy || editing || !status?.checker_ready}
          onClick={() => void check()}
        >
          {busy === 'checking' ? 'Checking claims…' : 'Recheck package'}
        </button>
      </div>
      {busy === 'loading' && <p role="status">Loading review status…</p>}
      {busy === 'checking' && (
        <p role="status">
          Checking every text unit against source passages. This may take a few minutes.
        </p>
      )}
      {status?.configuration_message && (
        <p className="ud-verification-warning" role="status">
          {status.configuration_message} Drafts remain available; verification and publishing stay
          locked.
        </p>
      )}
      {error && (
        <p className="ud-error" role="alert">
          {error}{' '}
          <button type="button" disabled={!!busy || editing} onClick={() => void check()}>
            Retry check
          </button>
        </p>
      )}
      {status?.report && (
        <>
          <div className="ud-validation-stats">
            <span>
              <strong>{supported}</strong> supported units
            </span>
            <span>
              <strong>{status.blocking_count}</strong> need attention
            </span>
            <span>
              <strong>
                {claims.reduce(
                  (n, claim) =>
                    n + claim.number_checks.filter((check) => check.status === 'matched').length,
                  0,
                )}
              </strong>{' '}
              numbers matched to evidence
            </span>
          </div>
          <p className="ud-validation-models">
            Writer: {status.report.writer_model} · Checker: {status.report.checker_model}. These are
            checker verdicts, not a measured accuracy score.
          </p>
          <label className="ud-review-checkbox">
            <input
              type="checkbox"
              checked={attentionOnly}
              onChange={(event) => {
                setAttentionOnly(event.target.checked)
                setShowPage(false)
              }}
            />
            Show only units needing attention
          </label>
          {filtered.length === 0 ? (
            <p role="status">
              No flagged units. Show all units to inspect their evidence before approving.
            </p>
          ) : (
            <div className="ud-evidence-workspace">
              <div className="ud-claim-list" aria-label="Checked text units">
                {filtered.map((claim) => (
                  <button
                    type="button"
                    key={claim.id}
                    className={current?.id === claim.id ? 'selected' : ''}
                    onClick={() => {
                      setSelected(claim.id)
                      setShowPage(false)
                    }}
                  >
                    <span className={`ud-verdict ${claim.verdict}`}>{labels[claim.verdict]}</span>
                    <small>
                      {claim.channel} · {claim.field}
                    </small>
                    <span>{claim.text}</span>
                  </button>
                ))}
              </div>
              {current && (
                <article className="ud-claim-proof">
                  <span className={`ud-verdict ${current.verdict}`}>{labels[current.verdict]}</span>
                  <h3>{current.text}</h3>
                  <p>{current.explanation}</p>
                  {current.suggested_revision && (
                    <div className="ud-suggested-revision">
                      <strong>Suggested correction</strong>
                      <p>{current.suggested_revision}</p>
                      <small>Use Edit text to apply it, then recheck.</small>
                    </div>
                  )}
                  {current.number_checks.length > 0 && (
                    <ul>
                      {current.number_checks.map((check, index) => (
                        <li key={index}>
                          {check.token}:{' '}
                          {check.status === 'matched'
                            ? 'found in linked evidence'
                            : check.status === 'missing_source'
                              ? 'absent from source'
                              : 'found elsewhere, missing from linked evidence'}
                        </li>
                      ))}
                    </ul>
                  )}
                  {current.evidence.map((evidence, index) => (
                    <div className="ud-evidence-excerpt" key={index}>
                      <strong>
                        {evidence.source_type === 'document'
                          ? evidence.page === null
                            ? 'DOCX source'
                            : `Source page ${evidence.page}`
                          : evidence.source_type === 'user'
                            ? 'User announcement — not independent evidence'
                            : 'Web source'}
                      </strong>
                      <blockquote>{evidence.excerpt}</blockquote>
                      {evidence.url && (
                        <a href={evidence.url} target="_blank" rel="noopener noreferrer">
                          Open web source ↗
                        </a>
                      )}
                    </div>
                  ))}
                  {!current.evidence.length && (
                    <p>No confirmed source passage was linked to this unit.</p>
                  )}
                  {firstPdf >= 0 && (
                    <>
                      <button
                        type="button"
                        className="ud-secondary-button"
                        onClick={() => setShowPage((value) => !value)}
                      >
                        {showPage ? 'Hide source page' : 'Show highlighted source page'}
                      </button>
                      {showPage && (
                        <img
                          className="ud-evidence-page"
                          src={`/api/verification/${runId}/evidence/${current.id}/${firstPdf}?v=${status.version}`}
                          alt={`Original PDF page with evidence highlighted where text positioning is available`}
                        />
                      )}
                    </>
                  )}
                </article>
              )}
            </div>
          )}
          <div className="ud-human-approval">
            <h3>Human approval</h3>
            <p>
              Correct every flagged unit and recheck. Review images, footage, narration and
              researcher quotes yourself; the text checker does not verify image pixels or uploaded
              footage.
            </p>
            {status.state === 'approved' && status.approval ? (
              <p className="ud-approved" role="status">
                Approved by {status.approval.reviewer} ·{' '}
                {new Date(status.approval.approved_at).toLocaleString()}. Changes require a new
                check and approval.
              </p>
            ) : (
              <>
                <label className="ud-reviewer-name">
                  Reviewer name
                  <input
                    value={reviewer}
                    onChange={(event) => setReviewer(event.target.value)}
                    maxLength={100}
                    placeholder="Your name"
                    disabled={!!busy || editing}
                  />
                </label>
                <label className="ud-review-checkbox">
                  <input
                    type="checkbox"
                    checked={claimsReviewed}
                    onChange={(event) => setClaimsReviewed(event.target.checked)}
                    disabled={!!busy || editing || status.blocking_count > 0}
                  />
                  I reviewed the claims, evidence, limitations and quotes.
                </label>
                <label className="ud-review-checkbox">
                  <input
                    type="checkbox"
                    checked={mediaReviewed}
                    onChange={(event) => setMediaReviewed(event.target.checked)}
                    disabled={!!busy || editing || status.blocking_count > 0}
                  />
                  I reviewed the selected images, video and narration (if present).
                </label>
                <button
                  type="button"
                  className="ud-primary-button"
                  disabled={
                    !!busy ||
                    editing ||
                    status.blocking_count > 0 ||
                    !claimsReviewed ||
                    !mediaReviewed ||
                    reviewer.trim().length < 2
                  }
                  onClick={() => void approve()}
                >
                  {busy === 'approving' ? 'Saving approval…' : 'Approve this version'}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </section>
  )
}
