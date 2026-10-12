import type { ComponentType } from 'react'
import type { CampaignBrief } from '../types/campaign'
import type { CombinedResult, MasterContent } from '../types/content'
import type { MediaAsset } from '../types/media'
import type { OutputLanguage, PlatformResult } from '../types/platform'

export type ExtensionContext = {
  readonly runId: string | null
  readonly language: OutputLanguage
  readonly brief: CampaignBrief
  readonly combined: CombinedResult | null
  readonly preview: PlatformResult | null
  readonly media: readonly MediaAsset[]
  readonly saveMaster: (content: MasterContent) => Promise<void>
  readonly saveBrief: (brief: CampaignBrief) => Promise<void>
}
export type ExtensionSlotName = 'source.tools' | 'review.top' | 'review.tools'
export type FeatureExtension = {
  id: string
  slot: ExtensionSlotName
  canRender?: (context: ExtensionContext) => boolean
  Component: ComponentType<{ context: ExtensionContext }>
}
