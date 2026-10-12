import { useRef, useState } from 'react'
import type { UploadedVideo } from '../types/video'

export default function VideoMedia({
  uploads,
  busy,
  onAdd,
  onDelete,
}: {
  uploads: UploadedVideo[]
  busy: boolean
  onAdd: (file: File) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const input = useRef<HTMLInputElement>(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  async function act(action: () => Promise<void>) {
    setWorking(true)
    setError('')
    try {
      await action()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update video clips.')
    } finally {
      setWorking(false)
    }
  }
  return (
    <section
      className="mt-8 rounded-xl border border-[#dce6f2] bg-[#f8fbff] p-5"
      aria-label="Your video clips"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Your video clips</h3>
          <p className="mt-1 text-xs text-slate-500">
            Optional MP4, MOV, or WEBM footage. Clips stay local and are used in the final edit.
          </p>
        </div>
        <>
          <input
            ref={input}
            type="file"
            accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void act(() => onAdd(file))
              event.target.value = ''
            }}
          />
          <button
            type="button"
            disabled={working || busy}
            onClick={() => input.current?.click()}
            className="rounded-lg border border-blue px-4 py-2 text-sm font-semibold text-blue disabled:opacity-50"
          >
            + Add video clip
          </button>
        </>
      </div>
      {busy && (
        <p className="mt-3 text-xs text-slate-500">
          Clip changes are available after the current video finishes.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {uploads.length > 0 && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {uploads.map((clip) => (
            <div
              key={clip.id}
              className="overflow-hidden rounded-lg border border-[#dce6f2] bg-white"
            >
              <video
                src={clip.url}
                controls
                preload="metadata"
                className="aspect-video w-full bg-black object-contain"
              />
              <div className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{clip.label}</p>
                  <p className="text-xs text-slate-500">
                    {clip.duration_seconds.toFixed(1)} seconds
                  </p>
                </div>
                <button
                  type="button"
                  disabled={working || busy}
                  onClick={() => void act(() => onDelete(clip.id))}
                  className="text-xs font-semibold text-red-700 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
