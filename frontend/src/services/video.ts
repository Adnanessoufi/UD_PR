import { request } from './content'
import type { UploadedVideo, VideoStatus } from '../types/video'

export const startVideo = (runId: string) => request<VideoStatus>(`/api/video/${runId}`)
export const regenerateVideo = (runId: string) =>
  request<VideoStatus>(`/api/video/${runId}/regenerate`)

export async function getVideoStatus(runId: string): Promise<VideoStatus> {
  const response = await fetch(`/api/video/${runId}/status`)
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.detail || 'Could not check video status.')
  return data as VideoStatus
}

export async function listVideoUploads(runId: string): Promise<UploadedVideo[]> {
  const response = await fetch(`/api/video/${runId}/uploads`)
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.detail || 'Could not load video clips.')
  return data as UploadedVideo[]
}

export async function uploadVideo(runId: string, file: File): Promise<UploadedVideo> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`/api/video/${runId}/uploads`, { method: 'POST', body: form })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.detail || 'Could not upload video clip.')
  return data as UploadedVideo
}

export const deleteVideo = (runId: string, id: string) =>
  request<UploadedVideo[]>(`/api/video/${runId}/uploads/${encodeURIComponent(id)}`, 'DELETE')
