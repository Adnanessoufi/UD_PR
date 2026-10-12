export type VideoStage =
  'idle' | 'planning' | 'narration' | 'generating_clips' | 'composing' | 'ready' | 'failed'

export type VideoStatus = {
  stage: VideoStage
  url: string | null
  error: string | null
  language?: 'en' | 'hu'
  model?: string
  clips_done?: number
  clips_total?: number
  clip_errors?: string[]
  duration_seconds?: number
  motion_ratio?: number
}

export type UploadedVideo = {
  id: string
  filename: string
  label: string
  duration_seconds: number
  url: string
}

export const videoBusy = (stage: VideoStage | undefined) =>
  stage === 'planning' ||
  stage === 'narration' ||
  stage === 'generating_clips' ||
  stage === 'composing'
