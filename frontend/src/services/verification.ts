import { request } from './content'
import type { ReviewContext, ReviewStatus } from '../types/verification'
export const getReviewStatus = (runId: string, context: ReviewContext) =>
  request<ReviewStatus>(`/api/verification/${runId}/status`, 'POST', context)
export const checkPackage = (runId: string, context: ReviewContext, force = false) =>
  request<ReviewStatus>(`/api/verification/${runId}/check`, 'POST', { ...context, force })
export const approvePackage = (
  runId: string,
  context: ReviewContext,
  version: string,
  reviewer: string,
) =>
  request<ReviewStatus>(`/api/verification/${runId}/approve`, 'POST', {
    context,
    approval: { version, reviewer, reviewed_claims: true, reviewed_media: true },
  })
