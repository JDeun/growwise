# Observed production UI and real Core journey

- Observed: 2026-11-03.
- Environment: macOS arm64, Python 3.12.13, Node 24.18.0, npm 11.16.0.
- Build: `npm run build` in `desktop/` completed; Vite 8.3.5, 129 modules.
- Run: `GROWWISE_E2E_ARTIFACTS=/tmp/growwise-live-artifacts node desktop/scripts/live_e2e.mjs`.
- Revision: modified working tree based on `5c92dac76c32a8910dee6461556354c822713d33`.
- Exact journey-script SHA256: `323fcfada659b0baccac493d66594733df6680166f3e130d8ea2ea40c745aeee`.
- Result: 13 asserted workflow steps passed; actual loaded production asset names are preserved in
  the [sanitized report](live-core-browser-20261103.json). No business API responses were mocked.
- Transport scope: a test-only same-origin IPC adapter forwards the production React UI to a real
  authenticated Core. Native Tauri IPC/process/OS dialogs are a separate verification target.
- Model scope: LLM, vision, embeddings and public enrichment were explicitly disabled. This is
  evidence for the deterministic/offline-capable product workflow, not real-model performance.
- Data: synthetic profiles and observations, independent reading record, reference note and the
  existing one-pixel PNG fixture; all data under a disposable directory, no household records.

Assertions include rejection of unauthenticated API access; first profile and material generation;
explicit parent use; exact saved result UUID; independent record kinds; provenance-backed Learning
Wiki and UI rebuild; an answer citing the saved result; confirmed conversation deletion preserving
another session and original records; direct lexical search; reference create/edit/detail/delete;
actual PNG upload/manual parent confirmation/saved image rendering; second-child private-scope
isolation and switching back; confirmed UI backup/restore preserving original child IDs, result,
independent record, conversation provenance and byte-identical photo bytes.

Screenshots for the completed result, observation timeline, grounded conversation, edited reference,
manual photo, second-child empty search, profile Wiki and restored timeline were inspected at
1440 x 1000. The synthetic photo is intentionally a one-pixel test image. Screenshots remain local;
no claims are made for all screen sizes, all OS WebViews, real family usability or learning gains.

The durable regression entry point is `npm run test:live` in `desktop/`; its dedicated CI workflow
runs a separate locked environment. The local run above does not claim that CI has already run.
