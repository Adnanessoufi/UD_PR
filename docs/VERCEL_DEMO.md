# The public demo on Vercel

[Open the public demo](https://ud-pr-studio.vercel.app).

The public site is a sample walkthrough. You can explore two fictional campaigns, switch the drafts between English and Hungarian, and check the source excerpts. You can edit the text in your tab and download it too.

The drafts, question answers and review examples are prepared in advance. The media includes illustrative posters and short videos with synthetic English narration and captions. None of it is evidence of a real study or an invitation to a real event.

## Deployment settings

Import `Adnanessoufi/UD_PR` into Vercel. Keep the project root at the repository root, not `frontend`. The root `vercel.json` supplies these settings:

| Setting | Value |
| --- | --- |
| Framework | Vite |
| Install command | `npm --prefix frontend ci` |
| Build command | `npm --prefix frontend run build:demo` |
| Output directory | `frontend/dist` |
| Public build variable | `VITE_DEMO_MODE=true` |

`frontend/.env.demo` already sets the demo variable for `build:demo`. It is safe to commit because it only contains that public setting. You can also set the same value in Vercel's environment settings. There are no secret variables to add for this version.

Keep OpenAI, ElevenLabs and social publishing credentials in the backend environment for the full app. Anything called `VITE_*` is included in the browser build, so API keys do not belong there.

Only `frontend/dist` is published. The Python backend, local uploads and saved campaigns are not part of this deployment. The demo does not call backend API routes. It does not let visitors upload files, use your API credits or publish posts. Edits disappear when the tab is refreshed. Download a copy if you want to keep them.

## Try it locally

From `frontend`:

```powershell
npm ci
npm run dev:demo
```

For the regular app, use `npm run dev` and start the Python backend as described in the main README. Make sure a local `.env` or `.env.local` doesn't override `VITE_DEMO_MODE` if you switch between the two versions.

## Check a change before deploying

```powershell
cd frontend
npm run test:demo
npm run build:demo
npm run format:check
```

The demo tests check that every sample excerpt appears in its source, all channels have bilingual drafts, and Vercel builds the sample version. Also check the page in a browser: edit a draft, restore it, switch samples, inspect the evidence and play both videos.

The MP4 files and captions are committed, so Vercel doesn't need to create media during a build. `scripts/render-demo-videos.py` can recreate the illustrated videos from six local WAV narration clips. Its docstring describes the filenames. The renderer uses the backend's Pillow and imageio-ffmpeg packages and Windows fonts; it isn't needed to run or deploy the demo.
