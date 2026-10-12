import type { PlatformName } from './platform'
export type ReviewContext = {
  platforms: PlatformName[]
  primary_media_id: string | null
  media_ids: string[]
}
export type Verdict = 'supported' | 'exaggerated' | 'unsupported' | 'needs_review' | 'non_factual'
export type Evidence = {
  passage_id: string
  source_type: 'document' | 'web' | 'user'
  page: number | null
  excerpt: string
  url: string | null
}
export type ClaimReview = {
  id: string
  channel: string
  field: string
  text: string
  verdict: Verdict
  explanation: string
  suggested_revision: string
  evidence: Evidence[]
  number_checks: { token: string; status: 'matched' | 'missing_source' | 'missing_evidence' }[]
}
export type ReviewStatus = {
  version: string
  state: 'unchecked' | 'needs_review' | 'verified' | 'approved'
  blocking_count: number
  checker_ready: boolean
  configuration_message: string | null
  report: {
    version: string
    checked_at: string
    writer_model: string
    checker_model: string
    context: ReviewContext
    claims: ClaimReview[]
  } | null
  approval: { version: string; reviewer: string; approved_at: string } | null
}
