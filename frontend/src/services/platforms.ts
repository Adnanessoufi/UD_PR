import { request } from './content'
import type { ContentType, OutputLanguage, PlatformName, PlatformResult } from '../types/platform'

export function generatePlatforms(
  runId: string,
  contentTypes: ContentType[],
  platforms: PlatformName[],
  language: OutputLanguage,
) {
  return request<PlatformResult>(`/api/platforms/${runId}`, 'POST', {
    content_types: contentTypes,
    platforms,
    language,
  })
}

export function savePlatforms(runId: string, result: PlatformResult) {
  return request<PlatformResult>(`/api/platforms/${runId}`, 'PUT', result)
}

export function regeneratePlatform(
  runId: string,
  contentTypes: ContentType[],
  platform: PlatformName,
  language: OutputLanguage,
) {
  return request<PlatformResult>(`/api/platforms/${runId}/regenerate`, 'POST', {
    content_types: contentTypes,
    platforms: [platform],
    language,
  })
}
