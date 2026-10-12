export type PublishedMedia = {
  id: string
  media_type: 'image' | 'video'
  asset_type: string
  label: string
  url: string
}

export type PublishedArticle = {
  run_id: string
  slug: string
  headline: string
  lead: string
  body: string
  published_at: string
  updated_at: string
  primary_media: PublishedMedia | null
  remaining_media: PublishedMedia[]
  source_title: string
  category: string
  article_url: string
}
