import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import type { MediaAsset } from '../types/media'
import type { PlatformName, PlatformPost } from '../types/platform'
import type { VideoStatus } from '../types/video'
import { VideoPlayer } from './VideoPanel'

type IconName = 'globe' | 'like' | 'heart' | 'comment' | 'repost' | 'share' | 'send' | 'save'

function Icon({
  name,
  className = 'h-5 w-5',
  filled = false,
}: {
  name: IconName
  className?: string
  filled?: boolean
}) {
  const paths: Record<IconName, ReactNode> = {
    globe: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
      </>
    ),
    like: (
      <path d="M7 10v11H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3Zm0 0 5-7a2 2 0 0 1 3 2l-1 4h6a2 2 0 0 1 2 2l-1 8a2 2 0 0 1-2 2H7" />
    ),
    heart: (
      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
    ),
    comment: (
      <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-4-.9L3 21l1.8-5.1a8.5 8.5 0 1 1 16.2-4.4Z" />
    ),
    repost: (
      <>
        <path d="m17 2 4 4-4 4M3 11V8a2 2 0 0 1 2-2h16M7 22l-4-4 4-4M21 13v3a2 2 0 0 1-2 2H3" />
      </>
    ),
    share: (
      <>
        <path d="m13 4 8 8-8 8M21 12H5a2 2 0 0 0-2 2v4" />
      </>
    ),
    send: (
      <>
        <path d="m22 2-7 20-4-9-9-4 20-7ZM11 13 22 2" />
      </>
    ),
    save: <path d="M5 3h14v18l-7-5-7 5V3Z" />,
  }
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {paths[name]}
    </svg>
  )
}

function Avatar({ size = 'h-11 w-11' }: { size?: string }) {
  return <img src="/ud-logo.png" alt="" className={`shrink-0 object-contain ${size}`} />
}

function MediaFrame({
  item,
  className = '',
  videoRef,
  poster,
}: {
  item: MediaAsset
  className?: string
  videoRef?: React.Ref<HTMLVideoElement>
  poster?: string
}) {
  return (
    <div className={`overflow-hidden bg-[#f7f9fc] ${className}`}>
      {item.media_type === 'video' ? (
        <video
          ref={videoRef}
          src={item.url}
          poster={poster}
          controls
          preload="metadata"
          playsInline
          aria-label={item.label}
          className="mx-auto block aspect-video w-full bg-black object-contain"
        />
      ) : (
        <img
          src={item.url}
          alt={item.label}
          className="mx-auto block max-h-[600px] w-full object-contain"
        />
      )}
    </div>
  )
}

export function carouselIndex(current: number, count: number, direction: -1 | 1): number {
  return count > 0 ? (current + direction + count) % count : 0
}

function MediaCarousel({
  media,
  platform,
}: {
  media: MediaAsset[]
  platform: 'linkedin' | 'facebook' | 'instagram'
}) {
  const [index, setIndex] = useState(0)
  const videoRef = useRef<HTMLVideoElement>(null)
  const active = media[index] || media[0]
  const position = media[index] ? index : 0
  useEffect(() => {
    const video = videoRef.current
    return () => video?.pause()
  }, [active?.id])
  if (!active) return null
  function show(index: number) {
    videoRef.current?.pause()
    setIndex(index)
  }
  return (
    <div
      className="bg-[#f7f9fc]"
      data-carousel-count={media.length}
      data-carousel-media={active.id}
    >
      <div
        className={`relative flex w-full items-center justify-center overflow-hidden ${platform === 'instagram' ? 'aspect-square border-y border-[#eee]' : 'aspect-video'}`}
      >
        {active.media_type === 'video' ? (
          <video
            key={active.id}
            ref={videoRef}
            src={active.url}
            controls
            preload="metadata"
            playsInline
            aria-label={active.label}
            className="h-full w-full bg-black object-contain"
          />
        ) : (
          <img src={active.url} alt={active.label} className="h-full w-full object-contain" />
        )}
        {media.length > 1 && (
          <>
            <button
              type="button"
              aria-label="Previous media"
              onClick={() => show(carouselIndex(position, media.length, -1))}
              className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-2xl leading-none text-ink shadow-md hover:bg-white"
            >
              ‹
            </button>
            <button
              type="button"
              aria-label="Next media"
              onClick={() => show(carouselIndex(position, media.length, 1))}
              className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-2xl leading-none text-ink shadow-md hover:bg-white"
            >
              ›
            </button>
          </>
        )}
      </div>
      <div className="flex items-center justify-center gap-3 border-t border-[#e7eaf0] px-3 py-2 text-xs font-semibold text-slate-500">
        <span aria-live="polite">
          {position + 1} / {media.length}
        </span>
        {media.length > 1 && (
          <div className="flex items-center gap-1.5" aria-label="Carousel positions">
            {media.map((asset, dot) => (
              <button
                key={asset.id}
                type="button"
                aria-label={`Show media ${dot + 1}`}
                aria-current={dot === position ? 'true' : undefined}
                onClick={() => show(dot)}
                className={`h-1.5 w-1.5 rounded-full ${dot === position ? 'bg-blue' : 'bg-slate-300'}`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SocialText({ post, showTitle = true }: { post: PlatformPost; showTitle?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const shortened = post.body.length > 175
  const text = shortened && !expanded ? `${post.body.slice(0, 172).trimEnd()}…` : post.body
  return (
    <div className="break-words text-[14px] leading-[1.65] text-[#202124]">
      {showTitle && post.title && <p className="mb-3 font-semibold">{post.title}</p>}
      <p className="whitespace-pre-wrap">{text}</p>
      {shortened && (
        <button
          type="button"
          className="mt-1 text-xs font-semibold text-[#5d6670] hover:underline"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'See less' : 'See more'}
        </button>
      )}
    </div>
  )
}

function Action({ icon, label }: { icon: IconName; label: string }) {
  return (
    <span className="flex min-w-0 items-center justify-center gap-1.5 text-xs font-semibold text-[#65717e] sm:text-sm">
      <Icon name={icon} className="h-[18px] w-[18px] shrink-0" />
      <span className="hidden sm:inline">{label}</span>
    </span>
  )
}

function LinkedInMockup({ post, media }: { post: PlatformPost; media: MediaAsset[] }) {
  return (
    <div className="min-w-0 bg-[#f3f2ef] px-3 py-8 sm:px-8" data-preview-platform="linkedin">
      <article className="mx-auto w-full max-w-[640px] overflow-hidden rounded-lg border border-[#d9dce0] bg-white shadow-sm">
        <div className="flex items-center gap-3 px-5 pb-3 pt-5">
          <Avatar />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[#1f2328]">University of Debrecen</p>
            <p className="text-xs text-[#6b7076]">University</p>
            <p className="flex items-center gap-1 text-xs text-[#6b7076]">
              Just now <span aria-hidden="true">·</span>{' '}
              <Icon name="globe" className="h-3.5 w-3.5" />
            </p>
          </div>
        </div>
        <div className="px-5 pb-5">
          <SocialText post={post} />
        </div>
        <MediaCarousel
          key={media.map((item) => `${item.id}:${item.url}`).join('|')}
          media={media}
          platform="linkedin"
        />
        <div
          aria-hidden="true"
          className="grid grid-cols-4 gap-1 border-t border-[#e7e9ec] px-2 py-4 sm:px-5"
        >
          <Action icon="like" label="Like" />
          <Action icon="comment" label="Comment" />
          <Action icon="repost" label="Repost" />
          <Action icon="send" label="Send" />
        </div>
      </article>
    </div>
  )
}

function FacebookMockup({ post, media }: { post: PlatformPost; media: MediaAsset[] }) {
  return (
    <div className="min-w-0 bg-[#f0f2f5] px-3 py-8 sm:px-8" data-preview-platform="facebook">
      <article className="mx-auto w-full max-w-[630px] overflow-hidden rounded-lg border border-[#e1e4e8] bg-white shadow-[0_2px_8px_rgba(40,50,70,0.08)]">
        <div className="flex items-center gap-3 px-5 pb-4 pt-5">
          <Avatar />
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-[#18202c]">University of Debrecen</p>
            <p className="flex items-center gap-1 text-xs text-[#687482]">
              Just now <span aria-hidden="true">·</span>{' '}
              <Icon name="globe" className="h-3.5 w-3.5" />
            </p>
          </div>
        </div>
        <div className="px-5 pb-5">
          <SocialText post={post} showTitle={false} />
        </div>
        <MediaCarousel
          key={media.map((item) => `${item.id}:${item.url}`).join('|')}
          media={media}
          platform="facebook"
        />
        <div className="flex items-center justify-between gap-3 border-t border-[#e4e7eb] px-5 py-2.5 text-[13px] text-[#626d7a]">
          <span className="flex items-center gap-2">
            <span className="flex -space-x-1" aria-label="Like, love and wow reactions">
              <span className="grid h-5 w-5 place-items-center rounded-full border border-white bg-[#1877f2] text-[11px]">
                👍
              </span>
              <span className="grid h-5 w-5 place-items-center rounded-full border border-white bg-[#f04b58] text-[11px]">
                ❤️
              </span>
              <span className="grid h-5 w-5 place-items-center rounded-full border border-white bg-[#ffbf36] text-[11px]">
                😮
              </span>
            </span>
            128 reactions
          </span>
          <span>12 comments · 18 shares</span>
        </div>
        <div className="grid grid-cols-3 border-t border-[#e4e7eb] px-5 py-3.5">
          <Action icon="like" label="Like" />
          <Action icon="comment" label="Comment" />
          <Action icon="share" label="Share" />
        </div>
      </article>
    </div>
  )
}

function InstagramMockup({ post, media }: { post: PlatformPost; media: MediaAsset[] }) {
  return (
    <div className="min-w-0 bg-[#fafafa] px-3 py-8 sm:px-8" data-preview-platform="instagram">
      <article className="mx-auto w-full max-w-[470px] overflow-hidden rounded-lg border border-[#dedede] bg-white shadow-sm">
        <div className="flex items-center gap-3 px-4 py-3">
          <Avatar size="h-9 w-9" />
          <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-[#181818]">
            universityofdebrecen_official
          </span>
          <span aria-hidden="true" className="px-1 text-xl leading-none text-[#292929]">
            ···
          </span>
        </div>
        <MediaCarousel
          key={media.map((item) => `${item.id}:${item.url}`).join('|')}
          media={media}
          platform="instagram"
        />
        <div
          className="flex items-center gap-4 px-4 pt-4 text-[#252525]"
          aria-label="Instagram preview actions"
        >
          <Icon name="heart" className="h-7 w-7 text-[#ed4956]" filled />
          <Icon name="comment" className="h-6 w-6" />
          <Icon name="send" className="h-6 w-6" />
          <Icon name="save" className="ml-auto h-6 w-6" />
        </div>
        <div className="break-words px-4 pb-5 pt-4 text-[13px] leading-[1.6] text-[#222]">
          <p className="font-semibold">342 likes</p>
          <p className="mt-2">
            <span className="mr-2 font-semibold">universityofdebrecen_official</span>
            {post.title && <span className="font-semibold">{post.title}</span>}
          </p>
          <p className="mt-1 whitespace-pre-wrap">{post.body}</p>
          <p className="mt-3 text-slate-500">View all 16 comments</p>
          <p className="mt-4 text-[10px] uppercase tracking-wide text-[#88909a]">Just now</p>
        </div>
      </article>
    </div>
  )
}

function WebsiteMockup({
  post,
  media,
  documentType,
}: {
  post: PlatformPost
  media: MediaAsset[]
  documentType: string
}) {
  const paragraphs = post.body
    .trim()
    .split(/\n\s*\n/)
    .filter(Boolean)
  const category =
    documentType === 'quick_announcement'
      ? 'Campus news'
      : /curriculum|programme|program|educational|degree/i.test(documentType)
        ? 'Education'
        : 'Research'
  const [hero, ...gallery] = media
  return (
    <article className="ud-article-preview" data-preview-platform="website">
      <header className="ud-article-top">
        <div className="ud-article-brand">
          <img src="/ud-logo.png" alt="" />
          <span>UNIVERSITY OF DEBRECEN</span>
        </div>
        <span>News</span>
      </header>
      <div className="ud-article-nav">
        <span>THE UNIVERSITY</span>
        <span>EDUCATION</span>
        <strong>RESEARCH</strong>
        <span>ABOUT UD</span>
      </div>
      <div className="ud-article-breadcrumb">Home&nbsp; › &nbsp;News&nbsp; › &nbsp;{category}</div>
      <div className="ud-article-body">
        <div className="ud-article-heading">
          <h2>{post.title}</h2>
          <time dateTime={new Date().toISOString().slice(0, 10)}>
            {new Intl.DateTimeFormat('en-GB', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            }).format(new Date())}
          </time>
        </div>
        {paragraphs[0] && <p className="ud-article-lead">{paragraphs[0]}</p>}
        {hero && (
          <figure className="ud-article-hero" data-website-hero={hero.id}>
            <MediaFrame item={hero} />
          </figure>
        )}
        <div className="ud-article-copy">
          {paragraphs.slice(1).map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
        {gallery.length > 0 && (
          <section className="ud-article-gallery" aria-label="Media gallery">
            <h3>Research visuals</h3>
            <div>
              {gallery.map((item) => (
                <figure key={item.id} data-gallery-media={item.id}>
                  <MediaFrame item={item} />
                  <figcaption>{item.label}</figcaption>
                </figure>
              ))}
            </div>
          </section>
        )}
      </div>
      <footer className="ud-article-footer">
        UNIVERSITY OF DEBRECEN <span>· News</span>
      </footer>
      <div className="ud-article-disclaimer">
        Hackathon demo — not the official University of Debrecen website
      </div>
    </article>
  )
}

function YouTubeMockup({
  post,
  media,
  video,
}: {
  post: PlatformPost
  media: MediaAsset[]
  video: VideoStatus | null
}) {
  const main =
    media.find((item) => item.asset_type === 'generated_video') ||
    media.find((item) => item.media_type === 'video')
  return (
    <article
      className="mx-auto max-w-[850px] overflow-hidden rounded-md border border-[#e6e9e6] bg-white"
      data-preview-platform="youtube"
    >
      <div className="flex items-center gap-2 border-b border-[#e6e9e6] px-5 py-3">
        <span
          className="grid h-6 w-8 place-items-center rounded-md bg-[#ff0033] text-[12px] text-white"
          aria-hidden="true"
        >
          ▶
        </span>
        <strong className="text-sm tracking-tight text-[#202124]">YouTube</strong>
        <span className="ml-auto text-xs text-slate-500">University of Debrecen</span>
      </div>
      {main ? (
        <MediaFrame item={main} />
      ) : (
        <VideoPlayer status={video?.stage === 'ready' ? null : video} />
      )}
      <div className="p-5">
        <h3 className="text-xl font-bold text-[#202124]">{post.title}</h3>
        <p className="mt-2 text-xs text-slate-500">1.4K views · Just now</p>
        <div className="mt-4 flex flex-wrap items-center gap-3 border-b border-[#e6e9e6] pb-4">
          <Avatar size="h-10 w-10" />
          <span className="text-sm font-semibold">University of Debrecen</span>
          <div className="ml-auto flex items-center gap-2 text-[#30353a]">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f2f3f3] px-3 py-2 text-xs font-semibold">
              <Icon name="like" className="h-4 w-4" />
              87 likes
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f2f3f3] px-3 py-2 text-xs font-semibold">
              <Icon name="share" className="h-4 w-4" />
              Share
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f2f3f3] px-3 py-2 text-xs font-semibold">
              <Icon name="save" className="h-4 w-4" />
              Save
            </span>
          </div>
        </div>
        <p className="mt-5 whitespace-pre-wrap text-sm leading-7 text-slate-700">{post.body}</p>
      </div>
    </article>
  )
}

function TikTokMockup({
  post,
  media,
  video,
}: {
  post: PlatformPost
  media: MediaAsset[]
  video: VideoStatus | null
}) {
  const main =
    media.find((item) => item.asset_type === 'generated_video') ||
    media.find((item) => item.media_type === 'video') ||
    (!video ? media.find((item) => item.media_type === 'image') : undefined)
  return (
    <article
      className="mx-auto max-w-[400px] overflow-hidden rounded-md bg-[#101214] text-white"
      data-preview-platform="tiktok"
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <Avatar size="h-9 w-9" />
        <span className="text-sm font-semibold">@universityofdebrecen_official</span>
        <span className="ml-auto text-xs font-semibold">TikTok</span>
      </div>
      <div className="tiktok-video-area relative">
        {main ? (
          <MediaFrame
            item={main}
            poster={media.find((item) => item.media_type === 'image')?.url}
            className="tiktok-media-frame"
          />
        ) : (
          <VideoPlayer status={video?.stage === 'ready' ? null : video} />
        )}
        <div
          className="absolute bottom-20 right-3 flex flex-col items-center gap-5"
          aria-label="TikTok preview reactions"
        >
          <span className="flex flex-col items-center gap-1 text-xs font-semibold">
            <Icon name="heart" className="h-8 w-8 text-[#ff3b5c]" filled />
            1.2K
          </span>
          <span className="flex flex-col items-center gap-1 text-xs font-semibold">
            <Icon name="comment" className="h-8 w-8 text-white" />
            23
          </span>
          <span className="flex flex-col items-center gap-1 text-xs font-semibold">
            <Icon name="share" className="h-8 w-8 text-white" />
            Share
          </span>
        </div>
      </div>
      <div className="p-5">
        <h3 className="font-semibold">{post.title}</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{post.body}</p>
      </div>
    </article>
  )
}

export default function PlatformMockup({
  platform,
  post,
  media,
  video = null,
  documentType = '',
}: {
  platform: PlatformName
  post: PlatformPost
  media: MediaAsset[]
  video?: VideoStatus | null
  documentType?: string
}) {
  if (platform === 'website')
    return <WebsiteMockup post={post} media={media} documentType={documentType} />
  if (platform === 'linkedin') return <LinkedInMockup post={post} media={media} />
  if (platform === 'facebook') return <FacebookMockup post={post} media={media} />
  if (platform === 'instagram') return <InstagramMockup post={post} media={media} />
  if (platform === 'youtube') return <YouTubeMockup post={post} media={media} video={video} />
  if (platform === 'tiktok') return <TikTokMockup post={post} media={media} video={video} />
  return (
    <div className="break-words rounded-xl border border-[#e3eaf2] bg-white p-6">
      <h3 className="text-xl font-semibold">{post.title}</h3>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">{post.body}</p>
    </div>
  )
}
