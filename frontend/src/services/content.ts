import type { CampaignBrief } from '../types/campaign'
import type { CombinedResult, MasterContent } from '../types/content'

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

export async function request<T>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'POST',
  body?: unknown,
  options?: { signal?: AbortSignal },
): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, {
      method,
      signal: options?.signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new Error('Could not reach the server. Please make sure the backend is running.')
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || 'Invalid field').join('; ')
          : detail?.message || 'The request could not be completed. Please retry.'
    throw new ApiRequestError(message, response.status)
  }
  return data as T
}

export const processDocument = (runId: string) => request<CombinedResult>(`/api/process/${runId}`)
export const loadSaved = (runId: string) => request<CombinedResult>(`/api/saved/${runId}`, 'GET')
export const generateMaster = (runId: string) => request<MasterContent>(`/api/generate/${runId}`)
export const saveMaster = (runId: string, content: MasterContent) =>
  request<MasterContent>(`/api/master/${runId}`, 'PUT', content)
export const createQuickAnnouncement = (
  text: string,
  runId: string,
  includeImages: boolean,
  language: 'en' | 'hu',
  brief?: CampaignBrief,
) =>
  request<{ run_id: string; combined: CombinedResult }>('/api/quick-announcements', 'POST', {
    text,
    run_id: runId,
    include_images: includeImages,
    language,
    brief,
  })
export const quickAnnouncementStatus = (runId: string) =>
  request<{ stage: string }>(`/api/quick-announcements/${runId}/status`, 'GET')
