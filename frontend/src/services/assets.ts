import { request } from './content'
import type { AssetPack } from '../types/assets'
import type { PlatformName } from '../types/platform'

export const generateAssets = (runId: string, platforms: PlatformName[]) =>
  request<AssetPack>(`/api/assets/${runId}`, 'POST', { platforms })

export const setMainAsset = (runId: string, assetId: string) =>
  request<AssetPack>(`/api/assets/${runId}/main`, 'PUT', { asset_id: assetId })

export const regenerateImage = (runId: string) =>
  request<AssetPack>(`/api/assets/${runId}/regenerate`)

export const deleteAsset = (runId: string, assetId: string) =>
  request<AssetPack>(`/api/assets/${runId}/${encodeURIComponent(assetId)}`, 'DELETE')

export async function uploadImage(runId: string, file: File): Promise<AssetPack> {
  const form = new FormData()
  form.append('file', file)
  let response: Response
  try {
    response = await fetch(`/api/assets/${runId}/upload`, { method: 'POST', body: form })
  } catch {
    throw new Error('Could not reach the server. Please make sure the backend is running.')
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.detail || 'Could not upload the image.')
  return data as AssetPack
}
