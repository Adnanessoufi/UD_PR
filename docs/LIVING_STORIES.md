# Living Stories

Readers can ask about a generated story in English or Hungarian and inspect the source behind the answer.

Open **Audience preview** from the campaign review screen. Choose a suggested question or enter your own. The answer includes source excerpts, an original-page viewer for PDFs and a reply draft you can copy.

The writer prepares an answer, a separate checker reviews it, and code confirms its quoted excerpts and numeric tokens. Saved answers are linked to the source version, question and language so the same question can reopen without another model call.

## Code

- Task: `story.answer`
- History: `GET /api/story-room/{run_id}/answers`
- PDF evidence: `GET /api/story-room/{run_id}/answers/{answer_id}/evidence/{index}`
- Backend module: `app/extensions/living_stories.py`
- UI module: `src/extensions/living-stories.tsx`

This is a local audience preview. It does not connect to a public social inbox or publish replies automatically. Review a reply before posting it.
