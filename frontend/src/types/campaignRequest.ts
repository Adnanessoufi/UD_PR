import type { ContentType, PlatformName, OutputLanguage } from './platform'
export type PlatformRequest = {
  content_types: ContentType[]
  platforms: PlatformName[]
  language: OutputLanguage
}
