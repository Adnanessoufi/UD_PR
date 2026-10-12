import { request } from './content'
import type { Job, TaskDescriptor } from '../types/job'
export const listTasks = () => request<TaskDescriptor[]>('/api/tasks', 'GET')
export const startJob = <T>(runId: string, taskId: string, args: Record<string, unknown> = {}) =>
  request<Job<T>>(`/api/jobs/runs/${runId}`, 'POST', { task_id: taskId, arguments: args })
export const getJob = <T>(id: string, signal?: AbortSignal) =>
  request<Job<T>>(`/api/jobs/${id}`, 'GET', undefined, { signal })
export const cancelJob = <T>(id: string) => request<Job<T>>(`/api/jobs/${id}/cancel`, 'POST')
export const retryJob = <T>(id: string) => request<Job<T>>(`/api/jobs/${id}/retry`, 'POST')
export const jobHistory = (runId: string) => request<Job[]>(`/api/jobs/runs/${runId}`, 'GET')
