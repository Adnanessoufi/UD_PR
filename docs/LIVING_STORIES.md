# Living Stories

Living Stories lets you ask questions about a generated story in English or Hungarian. You get an answer with excerpts from the source, so you can see what it's based on.

Open **Audience preview** from the campaign review screen. Try one of the suggested questions or write your own. If the source is a PDF, you can open the original page too. There's also a short reply draft you can copy.

One model writes the answer and a different model checks it. Code checks the quoted excerpts and numbers too. Saved answers are linked to the source version, question and language. Asking the same question again can reuse the saved answer instead of making another model call.

## Where it lives in the code

- Task: `story.answer`
- History: `GET /api/story-room/{run_id}/answers`
- PDF evidence: `GET /api/story-room/{run_id}/answers/{answer_id}/evidence/{index}`
- Backend module: `app/extensions/living_stories.py`
- UI module: `src/extensions/living-stories.tsx`

This is a local preview. It doesn't connect to a public social inbox or post replies for you. Read the reply and check the evidence before you use it.
