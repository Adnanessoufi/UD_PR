export type JobState = 'queued' | 'running' | 'ready' | 'failed' | 'cancelled' | 'interrupted'
export type Job<T = Record<string, unknown>> = {
  id: string
  run_id: string
  task_id: string
  label: string
  arguments: Record<string, unknown>
  state: JobState
  progress: number
  message: string
  attempt: number
  retry_of: string | null
  created_at: string
  updated_at: string
  result: T | null
  error: string | null
}
export type TaskDescriptor = {
  id: string
  label: string
  arguments_schema: Record<string, unknown>
  result_schema: Record<string, unknown>
  required_files: string[]
}
