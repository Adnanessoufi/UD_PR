import type { ContentType } from './platform'

export type ProcessingState = 'processing' | 'ready' | 'failed'

export type StageState = 'pending' | 'ready' | 'failed'
export type PackageProgress = {
  source: StageState
  platform: StageState
  image: StageState
  video: StageState
}

export function packageState(
  formats: ContentType[],
  progress: PackageProgress,
): 'waiting' | 'ready' | 'error' {
  const required = [progress.source, progress.platform]
  if (formats.includes('image')) required.push(progress.image)
  if (formats.includes('video')) required.push(progress.video)
  if (required.includes('failed')) return 'error'
  return required.every((stage) => stage === 'ready') ? 'ready' : 'waiting'
}
