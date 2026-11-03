# Final observed production UI and real Core journey

- Observed: 2026-11-03; status: observed.
- Supersedes [the earlier 13-step run](live-core-browser-20261103.md) for the final UI build; the earlier ledger entry remains unchanged.
- Environment: macOS arm64, Python 3.12.13, Node 24.18.0, npm 11.16.0.
- Run: `GROWWISE_E2E_ARTIFACTS=/tmp/growwise-live-artifacts-final node desktop/scripts/live_e2e.mjs` (`npm run test:live` is the durable equivalent).
- Revision: modified working tree based on `5c92dac76c32a8910dee6461556354c822713d33`.
- Journey-script SHA256: `7475cb45888edb716e82c97bc5337fc3daaf238e5ccb77d5efccf34426ca93f7`.
- Loaded assets: `index-DnarskrO.js`, `index-D6ORJyIj.css`.
- Outcome: 14 asserted steps passed; [sanitized report](live-core-browser-20261103-final.json).

The production React UI uses an IPC transport adapter to a real authenticated Core with isolated
synthetic data. No business responses are mocked. Existing checks retain exact result IDs,
conversation citations, child-scope isolation and restored photo bytes. The added selector check
creates two distinct materials through the UI, selects each native option, verifies its primary
heading and changed content, then selects the original again and compares its original content.

All nine screenshots were inspected at 1440 × 1000, including the visible primary selector,
material result, reading/observation view, Learning Wiki, conversation, reference edit, photo,
second-child empty search and restored records. The Wiki keeps human-readable text in its main
body and provenance behind the existing collapsed details. The photo is intentionally one pixel.
Screenshots stay local and contain only synthetic fixtures.

This run explicitly disables LLM, vision, embeddings and public enrichment. It establishes this
14-step deterministic workflow in one Chrome/macOS environment. Native IPC, OS dialogs, other
WebViews, model quality, real-family usability and educational effectiveness require separate
evidence. The local pass does not claim that remote CI has already run.
