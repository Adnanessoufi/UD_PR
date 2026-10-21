# UD PR Studio

I made UD PR Studio to help turn university research and news into something people can read without having to go through the whole paper first.

You give it a PDF, a Word document or a news article. You can also start with a short announcement. It prepares an article and posts for the channels you choose, in English or Hungarian. You can add images and narrated videos too.

You can go back to the source and see where a claim came from. There's a review step before publishing, because a draft sounding confident doesn't mean it got everything right.

## Have a look around

The public demo lets you explore two sample campaigns without installing anything or adding API keys. You can switch between English and Hungarian, edit the drafts and check the source excerpts. There are sample images and short narrated videos too.

The study and event in the demo are fictional, and the outputs are prepared in advance. For your own documents and live generation, run the full app locally using the steps below. The [Vercel setup notes](docs/VERCEL_DEMO.md) explain how the two versions work.

## What you can do with it

- Upload a PDF or DOCX, bring in a news article, or write a short announcement.
- Choose who you're writing for and how you want it to sound.
- Prepare text for a website, LinkedIn, Facebook, Instagram, TikTok or YouTube.
- Add images or make a narrated video with captions. Quick announcements support text and images.
- Edit the drafts and check their claims against the original source.
- Ask questions about a story, see the source excerpts behind the answer and copy a reply draft.
- Save a campaign to come back to later, or download its text and media.

## How the checking works

One model writes the draft. A different model checks its claims against the source, and code checks the quoted excerpts and numbers. You can open the evidence and fix anything that was flagged.

After that, a person reviews the text and selected media and approves that version. If you edit it, it needs another check and approval before you can publish.

That still doesn't make every claim correct. You need to review the images, uploaded footage and narration yourself too. The checks help you find problems; you still have to read what you're about to post.

I wrote more about this in [content validation](docs/VALIDATION_WORKFLOW.md). The question-and-answer feature is explained in [Living Stories](docs/LIVING_STORIES.md).

## Try it locally

You'll need Python 3.12, Node.js and npm. Video composition also uses FFmpeg through `imageio-ffmpeg`.

From the project folder, start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Add your API key and choose the writer and checker models in .env.
uvicorn app.main:app --reload --port 8001
```

Then open another terminal in the project folder and start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend sends API requests to the backend on port 8001. Your campaigns and generated media are saved locally in `backend/storage`.

Use different models for `OPENAI_MODEL` and `OPENAI_CHECKER_MODEL`. The app needs a separate checker before it can verify and approve a campaign. You can find the settings in [backend/.env.example](backend/.env.example).

## A few things to know

This is a prototype. Some parts need extra setup:

- ElevenLabs is needed for narration and video generation.
- Publishing to YouTube, TikTok, Facebook or Instagram needs the relevant credentials in `backend/.env`. Publishing can create real posts on connected accounts, so check the destination before using it.
- For LinkedIn, you can prepare and copy the text. Posting it is still up to you.
- The university website publisher saves to a local demo. It isn't connected to the university CMS.
- Living Stories is a local preview. It doesn't read a public social inbox or post replies for you.

Reviewer names are entered by the reviewer, so they aren't verified identities. Also, run one backend worker. The campaign locks and job queue live inside that process.

## If you're changing the code

The frontend uses React, TypeScript and Vite. The backend uses Python and FastAPI.

These are the checks I use:

```powershell
# These tests use mocked providers. They won't publish posts.
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Frontend build and formatting
cd ../frontend
npm run build
npm run format:check
```

For Python formatting, install `backend/requirements-dev.txt`, then run `ruff format backend/app backend/tests scripts` from the project folder. The frontend uses two-space indentation, single quotes and no semicolons.

Real keys, uploaded documents and generated media stay outside Git.
