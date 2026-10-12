# UD PR Studio

A university communication app that turns research papers, news and announcements into articles and social posts. It supports English and Hungarian, with images, narrated videos and source-backed review before publishing.

## Features

- Upload PDF or DOCX files, import news, or start from a short announcement.
- Set the audience, tone and language for a campaign.
- Generate website, LinkedIn, Facebook, Instagram, TikTok and YouTube copy.
- Create images and narrated videos with captions.
- Check claims against the source, inspect cited pages and approve the final package.
- Ask questions about a story and copy a source-backed reply.
- Save campaigns and export text or media packages.

## Run locally

Requirements: Python 3.12, Node.js and npm. Video composition also uses FFmpeg through imageio-ffmpeg.

Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Fill in your API key and writer/checker model settings in .env.
uvicorn app.main:app --reload --port 8001
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend forwards API requests to the backend on port 8001. Campaigns and generated media are stored locally in `backend/storage`.

ElevenLabs enables narration and video generation. YouTube, TikTok and Meta publishing need their own credentials; see `backend/.env.example`. LinkedIn currently supports copy generation. The university website publisher is a local demo, not a connection to the university CMS.

## Content review

The writer creates the draft; a different model checks its claims against the source. Code confirms the quoted excerpts and numeric values. A reviewer checks the text and media before approving that version. Edits invalidate the approval, and publishing routes check it again.

These checks help reviewers find problems; they are not a guarantee that every claim is correct. Images and uploaded footage still need human review. Reviewer names are self-declared in this prototype. Run a single backend worker because campaign locks and the job queue are local to that process.

More detail: [content validation](docs/VALIDATION_WORKFLOW.md) and [Living Stories](docs/LIVING_STORIES.md).

## Development

```powershell
# Backend tests use mocked providers and do not publish posts.
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Frontend build and formatting
cd ../frontend
npm run build
npm run format:check
```

Install `backend/requirements-dev.txt` for Python formatting, then run `ruff format backend/app backend/tests scripts` from the project root. Frontend code uses two-space indentation, single quotes and no semicolons.

New tools can use the existing task runner, campaign inputs and UI slots. See [extending the app](docs/EXTENDING_THE_APP.md).

Local credentials, uploaded documents, generated media and rehearsal backups are excluded from Git.
