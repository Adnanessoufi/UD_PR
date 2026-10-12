import type { UploadResult } from '../types/upload'

export function uploadDocument(
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    const data = new FormData()
    data.append('file', file)

    request.open('POST', '/api/upload')
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    request.onload = () => {
      let response: { detail?: string } & Partial<UploadResult>
      try {
        response = JSON.parse(request.responseText)
      } catch {
        reject(new Error('The server returned an unexpected response.'))
        return
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(response as UploadResult)
      } else {
        reject(new Error(response.detail || 'The document could not be processed.'))
      }
    }
    request.onerror = () =>
      reject(new Error('Could not reach the server. Please make sure the backend is running.'))
    request.send(data)
  })
}
