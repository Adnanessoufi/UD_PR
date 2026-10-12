import { useCallback, useEffect, useRef, useState } from 'react'
import { cancelJob, getJob, retryJob, startJob } from '../services/jobs'
import { ApiRequestError } from '../services/content'
import type { Job } from '../types/job'

/** Track a server job and restore it after refresh. */
export function useJob<T>(runId: string | null, taskId: string) {
  const [job, setJob] = useState<Job<T> | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const sequence = useRef(0)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      sequence.current++
    }
  }, [])
  const key = runId ? `ud-pr-job:${runId}:${taskId}` : null

  const accept = useCallback(
    (next: Job<T>) => {
      if (next.run_id !== runId || next.task_id !== taskId) return
      if (mounted.current) setJob(next)
      if (key) localStorage.setItem(key, next.id)
    },
    [runId, taskId, key],
  )

  useEffect(() => {
    sequence.current++
    setJob(null)
    setError('')
    setPending(false)
    const id = key ? localStorage.getItem(key) : null
    if (!id) return
    const controller = new AbortController()
    void getJob<T>(id, controller.signal)
      .then(accept)
      .catch((cause) => {
        if (controller.signal.aborted) return
        if (cause instanceof ApiRequestError && cause.status === 404 && key)
          localStorage.removeItem(key)
        setError(cause instanceof Error ? cause.message : 'Could not restore task status.')
      })
    return () => controller.abort()
  }, [key, accept])

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.state)) return
    const controller = new AbortController()
    let timer: number | undefined
    let delay = 700
    async function poll() {
      try {
        const next = await getJob<T>(job!.id, controller.signal)
        if (controller.signal.aborted) return
        accept(next)
        setError('')
        if (['queued', 'running'].includes(next.state)) {
          delay = Math.min(4000, Math.round(delay * 1.5))
          timer = window.setTimeout(() => void poll(), delay)
        }
      } catch (cause) {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Could not read task status.')
        timer = window.setTimeout(() => void poll(), 4000)
      }
    }
    timer = window.setTimeout(() => void poll(), delay)
    return () => {
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [job?.id, job?.state, accept])

  async function action(operation: () => Promise<Job<T>>) {
    const requestSequence = ++sequence.current
    setPending(true)
    setError('')
    try {
      const next = await operation()
      if (requestSequence === sequence.current) accept(next)
      return next
    } catch (cause) {
      if (requestSequence === sequence.current)
        setError(cause instanceof Error ? cause.message : 'Task request failed.')
      throw cause
    } finally {
      if (requestSequence === sequence.current) setPending(false)
    }
  }
  return {
    job,
    error,
    pending,
    start: (args: Record<string, unknown> = {}) => {
      if (!runId) return Promise.reject(new Error('Collect a source first.'))
      return action(() => startJob<T>(runId, taskId, args))
    },
    cancel: () =>
      job ? action(() => cancelJob<T>(job.id)) : Promise.reject(new Error('No task to cancel.')),
    retry: () =>
      job ? action(() => retryJob<T>(job.id)) : Promise.reject(new Error('No task to retry.')),
  }
}
