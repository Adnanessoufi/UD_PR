export type VisualAsset = {
  id: string
  type:
    | 'editorial_visual'
    | 'publication_preview'
    | 'source_visual'
    | 'generated_explainer'
    | 'programme_card'
    | 'generated_education_visual'
    | 'user_upload'
  label: string
  source: 'document' | 'local' | 'generated' | 'user' | 'web'
  path: string
  recommended: boolean
}

export type AssetPack = {
  document_family: 'research' | 'curriculum'
  assets: VisualAsset[]
  recommended_asset_id: string | null
  main_asset_id: string | null
  main_is_manual?: boolean
  image_attempted: boolean
  image_error: string | null
}

export function orderedAssets(pack: AssetPack | null): VisualAsset[] {
  if (!pack) return []
  const priority =
    pack.document_family === 'research'
      ? [
          'editorial_visual',
          'generated_explainer',
          'source_visual',
          'publication_preview',
          'user_upload',
        ]
      : ['generated_education_visual', 'programme_card', 'source_visual', 'user_upload']
  return pack.assets
    .map((asset, index) => ({ asset, index }))
    .sort((left, right) => {
      if (left.asset.id === pack.main_asset_id) return -1
      if (right.asset.id === pack.main_asset_id) return 1
      const rank = (type: VisualAsset['type']) => {
        const position = priority.indexOf(type)
        return position < 0 ? priority.length : position
      }
      return rank(left.asset.type) - rank(right.asset.type) || left.index - right.index
    })
    .map((item) => item.asset)
}
