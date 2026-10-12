import { request } from './content'
import type { CampaignBrief, CampaignBundle, CampaignSummary, NewsInbox } from '../types/campaign'
import type { PlatformRequest } from '../types/campaignRequest'
import type { UploadResult } from '../types/upload'
export const listCampaigns = (query = '', archived = false) =>
  request<CampaignSummary[]>(
    `/api/campaigns?query=${encodeURIComponent(query)}&archived=${archived}`,
    'GET',
  )
export const reopenCampaign = (id: string) => request<CampaignBundle>(`/api/campaigns/${id}`, 'GET')
export const updateCampaign = (
  item: CampaignSummary,
  changes: Partial<{ name: string; starred: boolean; archived: boolean }>,
) =>
  request<CampaignSummary>(`/api/campaigns/${item.run_id}`, 'PUT', {
    name: item.name,
    starred: item.starred,
    archived: item.archived,
    ...changes,
  })
export const saveBrief = (id: string, brief: CampaignBrief) =>
  request<CampaignBrief>(`/api/campaigns/${id}/brief`, 'PUT', brief)
export const saveWorkspace = (id: string, selection: PlatformRequest) =>
  request(`/api/campaigns/${id}/workspace`, 'PUT', selection)
export const getNewsInbox = () => request<NewsInbox>('/api/news/inbox', 'GET')
export const collectFeeds = (urls: string[]) =>
  request<NewsInbox>('/api/news/feeds', 'POST', { urls })
export const importArticle = (url: string) =>
  request<UploadResult>('/api/news/import', 'POST', { url })
