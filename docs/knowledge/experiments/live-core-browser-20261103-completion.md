# Observed expanded production UI and actual Core journey

- Observed:2026-11-03; status:observed;18 asserted steps passed.
- Revision:modified working tree based on `e3c3b3b19d9fa23a42d976e39f7fee48af211d4b`.
- Script SHA256:`6314500f9ccd15db3c01fe86a4cf0aca08e48f282645b953bb342f2049f0b95e`.
- Build:`index-DgKRkCJj.js`, `index-CgZeVefP.css`; exact asset hashes in the [sanitized report](live-core-browser-20261103-completion.json).
- Command:`GROWWISE_E2E_ARTIFACTS=/tmp/growwise-live-completion-final node desktop/scripts/live_e2e.mjs`.
- Environment:macOS arm64, Python3.12.13, Node24.18.0, npm11.16.0.
- Supersedes the [earlier14-step frozen-build run](live-core-browser-20261103-final.md) for expanded scope; old artifacts and ledger rows remain unchanged.

The production React UI connects through a test IPC adapter to an actual authenticated Core with
isolated synthetic data. Business responses are not mocked. For the stale-response test, actual
learning/study responses for child A are deliberately delayed until child B has loaded; the late
responses cannot replace B's records. Normal source citation, reading/observation, resource CRUD,
photo, second-child isolation and byte-preserving restore checks remain present.

Additional assertions cover first-run profile creation at860×620 with its save CTA inside the
viewport; optional book/AIhint/true-or-false evidence/reexplanation fields; current-original source
disclosure; global reference creation followed by metadata edit and private scope; primary print;
and conversation proposal → visible book/topic handoff → explicit parent generation of an
unapproved draft. A proposal alone creates no material and never bypasses Parent Review.

The print check spies on `window.print` to verify the primary action, then uses Chrome print media
and `Page.printToPDF` to generate an actual8-page PDF (441003bytes). It checks the one-document
scope, required guide visibility and restoration of previously open/closed details. This is a real
browser PDF, not evidence that a native OS print dialog was exercised. Native default-browser source
opening has a separate manually run Rust smoke test and is not inferred from this IPC-adapted run.

All17 successful-run PNGs were inspected: first empty home, minimum-window profile, primary print,
material result, document selector, optional result form, saved false-evidence history, independent
true-evidence detail, timeline, Wiki, conversation/original source, reference metadata, manual photo,
second-child empty search, restored records and delayed-child responses. The original reader now
shows human-readable saved text and a formatted event date without duplicate technical enum/time
metadata. The one-pixel photo is an intentional synthetic fixture. Images and PDF stay local; the
repository contains only sanitized names, counts and hashes.

LLM, vision, embeddings and public enrichment are disabled. Date/axis search and growth event-date
semantics have separate focused API/service tests. Selective child/date raw-record export is a later
explicit requirement outside this18-step run. This run does not prove every possible UI state,
Windows WebView behavior, household usability, model quality, educational effectiveness or remote
CI success for a later commit.
