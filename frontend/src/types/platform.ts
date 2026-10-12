export type ContentType = 'text' | 'image' | 'video'
export type OutputLanguage = 'en' | 'hu'
export type PlatformName = 'website' | 'linkedin' | 'facebook' | 'instagram' | 'tiktok' | 'youtube'

export type PlatformPost = {
  platform: PlatformName
  title: string
  body: string
  source_fact_ids: string[]
}

export type PlatformResult = {
  content_types: ContentType[]
  platforms: PlatformName[]
  language: OutputLanguage
  items: PlatformPost[]
}

export const platformLabels: Record<PlatformName, string> = {
  website: 'University Website',
  linkedin: 'LinkedIn',
  facebook: 'Facebook',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
}

export const platformOrder: PlatformName[] = [
  'website',
  'linkedin',
  'facebook',
  'instagram',
  'tiktok',
  'youtube',
]

export function platformAvailability(
  platform: PlatformName,
  types: ContentType[],
  quickAnnouncement = false,
): { enabled: boolean; reason: string } {
  const has = (type: ContentType) => types.includes(type)
  if (platform === 'website') return { enabled: has('text'), reason: 'Select Text to enable' }
  if (platform === 'instagram')
    return { enabled: has('image') || has('video'), reason: 'Select Image or Video to enable' }
  if (platform === 'tiktok' && quickAnnouncement)
    return { enabled: has('text'), reason: 'Select Text to enable a caption preview' }
  if (platform === 'tiktok' || platform === 'youtube')
    return { enabled: has('video'), reason: 'Select Video to enable' }
  return { enabled: types.length > 0, reason: 'Choose a content format first' }
}
