# Content validation

A campaign goes through writing, checking and human review before publishing.

## Checks

1. The writer creates the master story and channel drafts.
2. A different checker model compares text units with original source passages, including selected video narration and overlays.
3. Code confirms each quoted excerpt and checks numeric tokens against the linked evidence.
4. The review panel shows verdicts, suggested corrections and source excerpts. PDF citations can open a highlighted page; DOCX and web sources show excerpts.

A number appearing somewhere in a paper is not enough. It must also occur in the cited evidence. Units, causality and missing qualifiers require the model's semantic check and the reviewer's judgment.

## Approval

The reviewer enters a name and confirms review of the text and selected media. `verification.json` and `approval.json` are saved with the campaign.

A fingerprint ties the review to the source, content, language, models, checker prompt, selected channels and media bytes. Changes make the review stale. A forced recheck also needs fresh approval. Publishing endpoints enforce this check on the server.

Campaign mutations share a lock so edits cannot race approval or publishing within one backend process.

## Limits

Checker verdicts are not an accuracy measurement. The numeric check covers digit-based values; spelled-out quantities and ambiguous units still need review. Uploaded images and footage are not checked at the pixel level. User announcement text is not independent evidence.

Reviewer names are self-declared. A shared deployment would need authentication and shared locking. The local website publisher is a demo.

## Tests

The backend tests cover invalid numbers, fabricated quotes, missing checker output, stale approvals, changed media and blocked publishing. Providers are mocked. The evaluation runner in `app/scripts/evaluate_factuality.py` can run labelled cases separately from the regression suite.
