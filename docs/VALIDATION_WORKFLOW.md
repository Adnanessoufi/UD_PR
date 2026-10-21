# Content validation

The app writes a draft, checks it against the source and asks a person to review it before publishing. Here's what happens at each step.

## Checks

1. The writer creates the master story and channel drafts.
2. A different model compares each part of the text with the original source. This includes the selected video's narration and overlays.
3. Code checks whether the quoted excerpts are actually in the source and whether the numbers appear in the linked evidence.
4. You can see the verdicts and source excerpts in the review panel, along with suggested corrections. For PDFs, you can open a highlighted page. DOCX and web sources show excerpts.

A number being somewhere in the paper isn't enough. It has to appear in the evidence linked to that claim. Even then, the same number can mean different things. The model and reviewer still need to check the units, what caused what and any limits the draft left out.

## Approval

Enter your name and confirm that you've reviewed the text and selected media. The app saves `verification.json` and `approval.json` with the campaign.

The review has a fingerprint tied to the source and generated content. It also covers the language, model settings, checker prompt, selected channels and media bytes. If any of these change, you'll need a new check and approval. Forcing a recheck also means approving again. The server checks this before publishing.

Changes to a campaign share a lock, so an edit can't happen at the same time as approval or publishing within one backend process.

## Limits

The verdicts tell you what the checker decided. They don't measure how accurate it is. The number check covers values written as digits, so written-out quantities and unclear units still need review. The text checker can't verify what's shown in uploaded images or footage. A user's announcement also isn't independent evidence for its own claims.

Anyone can enter a reviewer name in this prototype. A shared deployment would need sign-in and locks that work across backend processes. The website publisher currently saves to a local demo.

## Tests

The backend tests cover invalid numbers and made-up quotes, along with missing checker output, stale approvals, changed media and blocked publishing. They use mocked providers. You can run labelled evaluation cases separately with `app/scripts/evaluate_factuality.py`.
