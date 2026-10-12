import type { CombinedResult } from './content'
import type { AssetPack } from './assets'
import type { PlatformResult, PlatformName, ContentType, OutputLanguage } from './platform'
import type { UploadResult } from './upload'
import type { UploadedVideo, VideoStatus } from './video'
export type CampaignBrief = {
  audience: 'general_public' | 'students' | 'industry' | 'researchers'
  tone: 'institutional' | 'friendly' | 'energetic'
  length: 'short' | 'standard' | 'detailed'
  focus: string
  call_to_action: string
}
export const defaultBrief: CampaignBrief = {
  audience: 'general_public',
  tone: 'institutional',
  length: 'standard',
  focus: '',
  call_to_action: '',
}
export type CampaignSummary = {
  run_id: string
  name: string
  title: string
  source_kind: string
  filename: string
  source_url: string | null
  language: OutputLanguage
  platforms: PlatformName[]
  status: string
  starred: boolean
  archived: boolean
  updated_at: string
}
export type CampaignBundle = {
  info: CampaignSummary
  run: UploadResult
  combined: CombinedResult | null
  preview: PlatformResult | null
  assets: AssetPack | null
  video_status: VideoStatus | null
  video_uploads: UploadedVideo[]
  workspace: { content_types: ContentType[]; platforms: PlatformName[]; language: OutputLanguage }
  brief: CampaignBrief
}
export type NewsItem = {
  id: string
  title: string
  url: string
  summary: string
  published: string
  feed_url: string
}
export type NewsInbox = {
  feeds: string[]
  items: NewsItem[]
  refreshed_at: string | null
  added?: number
  errors?: { url: string; message: string }[]
}
