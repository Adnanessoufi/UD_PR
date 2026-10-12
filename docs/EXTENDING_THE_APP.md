# Adding a tool

Each feature has a backend module and a frontend panel. The shared task runner handles progress, saved job results, cancellation and retries.

## Create a starter

From the project root:

```powershell
python scripts/new-extension.py my-feature --label "My feature" --slot review.tools
```

This creates a backend handler, prompt file, React panel and a short README. It stays inactive until implemented.

1. Edit `implement(campaign, args)` in `backend/app/extensions/my_feature.py`.
2. Adjust the input and result models. Keep the frontend request and Result type in sync.
3. Set the required files and panel visibility to match the feature.
4. Enable it with `python scripts/new-extension.py my-feature --activate-existing`.
5. Restart the backend, run a relevant fixture and build the frontend.

Existing files are never overwritten. An unfinished handler returns an implementation error rather than placeholder results.

## Campaign inputs and storage

```python
campaign = context.campaign()
passages = campaign.source_passages()
await context.report(20, "Reading source")

store = context.store("my-feature")
inputs = {"campaign": campaign.fingerprint("source", "analysis"),
          "arguments": args.model_dump(), "implementation_version": 1}
cached = store.read("result", MyResult, inputs=inputs)
store.write("result", result, inputs=inputs)
```

Campaign inputs include source text, analysis, master content, channel drafts, brief and language. Source passages preserve PDF pages and original web URLs.

Results are saved under `backend/storage/<run>/extensions/<feature>`. Changed inputs or schema versions produce a cache miss. The starter includes the prompt text and `IMPLEMENTATION_VERSION`; increase that version when handler behavior changes.

Use the existing model gateway for structured AI calls, or ordinary Python for transformations and algorithms. Store results, not credentials.

## Registration and UI

Backend modules are listed in `app/extensions/__init__.py`. They register tasks and can export a FastAPI router. Frontend modules are listed in `src/extensions/index.ts`.

| Slot | Position |
| --- | --- |
| `source.tools` | After the campaign brief |
| `review.top` | Above the platform preview |
| `review.tools` | After media, before export and validation |

Panels receive the campaign data, selected media and existing save callbacks. Each panel has an error boundary; async errors still need normal handling. Living Stories uses this structure as a working example.

New source tabs or special workflows can still need changes to the main screen. Keep external publishing behind the existing validation and human approval checks.
