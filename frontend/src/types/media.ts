import type { AssetPack, VisualAsset } from './assets'
import type { UploadedVideo, VideoStatus } from './video'

export type MediaAsset = {
  id: string
  media_type: 'image' | 'video'
  asset_type: VisualAsset['type'] | 'generated_video' | 'uploaded_video'
  label: string
  url: string
  source: VisualAsset['source']
  recommended: boolean
  primary: boolean
}

export function orderedMediaAssets(
  pack: AssetPack | null,
  video: VideoStatus | null,
  uploads: UploadedVideo[],
  includeImages: boolean,
  includeVideo: boolean,
  manualPrimaryId: string | null,
  hideGeneratedVideo: boolean,
): MediaAsset[] {
  const items: MediaAsset[] = []
  if (includeVideo && !hideGeneratedVideo && video?.stage === 'ready' && video.url) {
    items.push({
      id: 'generated_video',
      media_type: 'video',
      asset_type: 'generated_video',
      label: 'Generated video',
      url: video.url,
      source: 'generated',
      recommended: true,
      primary: false,
    })
  }
  if (includeImages && pack) {
    items.push(
      ...pack.assets.map((asset) => ({
        id: asset.id,
        media_type: 'image' as const,
        asset_type: asset.type,
        label: asset.label,
        url: asset.path,
        source: asset.source,
        recommended: asset.recommended,
        primary: false,
      })),
    )
  }
  if (includeVideo) {
    items.push(
      ...uploads.map((clip) => ({
        id: `uploaded_video:${clip.id}`,
        media_type: 'video' as const,
        asset_type: 'uploaded_video' as const,
        label: clip.label,
        url: clip.url,
        source: 'user' as const,
        recommended: false,
        primary: false,
      })),
    )
  }
  const priority =
    pack?.document_family === 'curriculum'
      ? [
          'generated_video',
          'generated_education_visual',
          'programme_card',
          'source_visual',
          'user_upload',
          'uploaded_video',
        ]
      : [
          'editorial_visual',
          'generated_video',
          'generated_explainer',
          'source_visual',
          'publication_preview',
          'user_upload',
          'uploaded_video',
        ]
  const rank = (type: MediaAsset['asset_type']) => {
    const index = priority.indexOf(type)
    return index < 0 ? priority.length : index
  }
  const officialProfile = pack?.assets.find(
    (asset) => asset.source === 'web' && asset.label === 'Official profile photo',
  )
  const requestedPrimary =
    manualPrimaryId || (pack?.main_is_manual ? pack.main_asset_id : officialProfile?.id || null)
  const primaryId =
    requestedPrimary && items.some((item) => item.id === requestedPrimary)
      ? requestedPrimary
      : [...items].sort((a, b) => rank(a.asset_type) - rank(b.asset_type))[0]?.id
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      if (a.item.id === primaryId) return -1
      if (b.item.id === primaryId) return 1
      return rank(a.item.asset_type) - rank(b.item.asset_type) || a.index - b.index
    })
    .map(({ item }) => ({ ...item, primary: item.id === primaryId }))
}
