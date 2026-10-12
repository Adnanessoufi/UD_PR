import type { Job } from '../types/job'
type Props = {
  job: Job<unknown> | null
  error?: string
  pending?: boolean
  onCancel?: () => void
  onRetry?: () => void
}
export default function JobStatusCard({ job, error, pending = false, onCancel, onRetry }: Props) {
  if (!job && !error && !pending) return null
  const active = job && ['queued', 'running'].includes(job.state)
  const retryable = job && ['failed', 'interrupted', 'cancelled'].includes(job.state)
  return (
    <section aria-label="Task progress" className="sprint-media-progress">
      <strong>{job?.label || 'Preparing task'}</strong>
      {job && (
        <>
          <p role="status">{job.message}</p>
          <progress
            aria-label="Task progress"
            value={job.progress}
            max={100}
            style={{ width: '100%', accentColor: '#124a39' }}
          />
        </>
      )}
      {(error || job?.error) && (
        <p role="alert" className="ud-error">
          {error || job?.error}
        </p>
      )}
      <div className="sprint-inline-actions">
        {active && onCancel && (
          <button
            type="button"
            className="ud-secondary-button"
            disabled={pending}
            onClick={onCancel}
          >
            Cancel
          </button>
        )}
        {retryable && onRetry && (
          <button
            type="button"
            className="ud-secondary-button"
            disabled={pending}
            onClick={onRetry}
          >
            Retry
          </button>
        )}
      </div>
    </section>
  )
}
