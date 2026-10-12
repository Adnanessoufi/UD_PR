export type UploadResult = {
  run_id: string
  filename: string
  file_type: 'pdf' | 'docx' | 'announcement' | 'news'
  page_count: number | null
  status: 'ready'
  cached?: boolean
}
