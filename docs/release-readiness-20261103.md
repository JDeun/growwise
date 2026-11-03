# Release readiness assessment — 2026-11-03

Current scope: **unsigned GitHub prerelease installers and source for `0.1.0-alpha.0`**.
Local V7 Core validation has passed. Three-platform package CI, actual Windows WebView execution
and the Linux navigation-soak memory finding still require a successful final run. This assessment
covers `974e512` plus the current working-tree corrections; it does not claim that all remote checks
have passed or that a release has already been published.

The user explicitly chose an unsigned initial public prerelease. Platform certificates, notarization
and a durable updater signing key are later **signed stable release** requirements, not prerequisites
for this initial scope. The updater remains truthfully `notconfigured`; no private key was generated.
Existing signed stable-tag gates remain enforced.

## Eight audit findings

| Finding | Implemented resolution | Validation scope |
| --- | --- | --- |
| Deleted/edited RAG bodies could enter model prompts after projection cleanup failed | Current Markdown snapshots, current visibility/grants and bounded original text replace cached chunk bodies in context, direct RAG and the original reader; derived Wiki also requires current source fingerprints and grants | Deletion/edit/revocation/narrowing/delay/raw-source/derived-Wiki regressions; final V7 Python suite passes |
| Terminally interrupted photos could remain processing | Photo recovery reconciles source status and terminal/interrupted jobs | Recovery and retry regressions; final V7 Python suite passes |
| Gallery loaded24originals, up to480MiB | Bounded metadata-free JPEG thumbnails, authenticated native/API access, original handling only when needed and URL cleanup | Thumbnail/privacy/UI regressions; fresh frozen V7 Core actually creates a synthetic PNG photo and returns a bounded JPEG |
| Overlapping photo polls invalidated generations and starved completion | Completion-driven serial polling and current-child guards | Polling/UI regressions and actual-Core browser journeys |
| Development dependencies had36reports/31unique advisory IDs across5packages | Locked dependency updates | Final local full development-environment pip-audit reports0known vulnerabilities; the local GrowWise project is not a PyPI package and is skipped. npm runtime audit also reports0 |
| limit8 decoded the full corpus | SQL/filter/limit paths decode only selected payloads | One synthetic10k local comparison:142.27ms/67,340,086B peak to17.14ms/60,459B,8decodes; not a hardware guarantee |
| Embedding-model changes synchronously reembedded the corpus | Single background worker,32-row pages, no waiting refresh queue, generation fences and lexical fallback | Worker/model-change regressions; final V7 Python suite passes |
| Recovery mixed limits for different job types | Photo and background-AI recovery apply their configured job-specific limits | Recovery regressions; final V7 Python suite passes |

The final local V7 Python run passed2338tests with1optional denylist skip. One third-party Starlette
`BlockingPortal` deprecation warning remains. The new canonical-child controller additionally has
14focused store/context/App tests, including delayed responses, explicit selections, new profiles,
reordered restore lists, provider reloads and unavailable storage. Frontend production compilation
and lint pass. Earlier whole-frontend run131files/298tests preceded the final additional storage test;
this document does not relabel that run as a later aggregate.

## Additional findings resolved in code

The App no longer owns a second child list/selection. A single provider owns selection, request
generations reject late lists and child-keyed controllers fence old in-flight work. Parent save
notices remain outside the child-key boundary. The actual authenticated-Core browser journey passed
21steps after this correction, including restoration/reload, child isolation, original citation
reading, selected raw export and infant guide printing. Its subsequent local navigation soak passed
34cycles over2minutes. The earlier15minute macOS soak is separate evidence; it does not prove Linux
memory stability, where a new CI measurement remains under investigation.

Search ordering and material-request intent parsing now use linear scans instead of repeated
wildcard searches.20,000character hostile-prefix regressions pass. Low-level photo store/delete
operations canonicalize child UUIDs before filesystem I/O and reject symlink destinations. Retrieval
cleanup logs no longer include the user-supplied source identifier. These changes have83focused
regression tests plus Ruff/mypy validation.

The updater has explicit Settings check/download/install/restart controls and confirmed native
commands. Downloads require HTTPS, bounded size and a valid signature/signed app version before
stopping Core. Failure restarts Core; installation is serialized with storage/model/key changes.
The modal stays open and blocks unrelated input until restart or failure. Real-browser focus,
Tab/Escape/backdrop checks and local bad-signature/interrupted-download fixtures pass. These use
public/synthetic fixtures and do not establish a production-key update chain. Initial prerelease
builds without a durable public trust root expose `notconfigured` rather than a working update claim.

## Current CI findings and fixes

- Previous four-platform sidecar/package smoke failures came from the harness reading the photo
  response at the wrong level. It now reads the real `{record, assets, job}` envelope. A real API
  regression and fresh local frozen-Core handshake/authentication/PNG-to-JPEG checks pass.
- The latest macOS arm64/x64 packages and Ubuntu sidecar job stopped at the strict interpreter
  notice guard. uv0.12.13 selected Python3.12.13+20260807, whereas the reviewed interpreter and native
  notices were3.12.13+20260623. CI now installs from official commit-pinned download metadata into an
  isolated managed directory before syncing. An actual fresh download using uv0.12.13 reproduced the
  intended June23build and OpenSSL3.5.7. The guard stays strict and reports the actual runtime on mismatch.
- The latest Windows package compiled the updater test binary but its loader exited with
  `0xc0000139` before the harness started. This remains unresolved until the loader diagnosis and
  corrected Windows package run succeed. The separate default-feature Windows Rust tests passed.
- CodeQL workflow execution and gitleaks checks passed on the reviewed PR snapshot. The remaining
  CodeQL alert16 was individually reviewed and dismissed as `used in tests`: synthetic harness files
  are sent only to an explicitly validated `ws://127.0.0.1:<port>/devtools/` Chrome endpoint, protected
  by2protocol regressions. No broad query/path suppression was added. This is bounded triage, not a
  claim of universal absence of security defects.

## Packaged attribution and clean build

Core builds reject development-tool contamination, follow the actual runtime dependency graph and
copy full LICENSE/NOTICE/copyright texts verbatim. Reviewed official version/commit overrides cover
packages that omit their own license files. The complete local bundle verifies376rows:57Python,
2bootloader-support,4Node,311Rust packages, one native-interpreter component group and one Rust
standard-library credit group. The Rust standard-library file is the installed toolchain's full
`COPYRIGHT-library.html`. Python's group includes8distributor component notices and the exact
OpenSSL3.5.7 LICENSE/AUTHORS texts. Every copied file has SHA-256 and source provenance. This preserves
provided terms technically; it is not a complete legal opinion.

The clean V7 PyInstaller build and complete376-row bundle verification passed. Its actual frozen
Core then passed protocol1handshake, rejection of unauthenticated requests, core-only health and
synthetic PNG-to-bounded-JPEG conversion. Windows/macOS installer success still depends on the final
package CI; local sidecar success is not relabeled as cross-platform installation evidence.

## Educational quality and later operational limits

The [repeated model experiment](knowledge/experiments/model-repeat-quality-20261103.md) retains all
51actual model calls, including failed pilots, and distinguishes later V7 replay of those saved
responses from new inference. The earlier mistranslation of `How are you?` is retained as historical
failed evidence. Current targeted gates/scaffolds reject or repair the observed classes, with honest
reviewable fallbacks; they are not a general translation, factual correctness or child-safety proof.
The final24-call observed cohort contains22AI-enhanced outputs and2reviewable template fallbacks.
Agent review of synthetic material is not parent approval, teacher evaluation or learning efficacy.

No paid remote-compatible AI account or personal provider credential was used for a live external
API call. API-key/native storage and connection contracts have tests; those tests do not establish
successful operation with every paid remote account or external service environment.

A physical Windows device, representative minimum/recommended hardware and longitudinal household
use remain unverified. Windows cloud WebView tests are valuable execution evidence but cannot stand
in for every installed-device, OS-store or recovery scenario. Real signed stable-client update tests
remain a later operational requirement. No household records, personal API keys or private signing
material belong in public evidence.

See [release gates](RELEASE_READINESS.md), [release operations](release.md),
[operator handoff](operator-handoff.md), [privacy boundaries](privacy-and-safety.md) and
[material quality contract](material-quality-contract.md). Append-only research evidence remains
unchanged; current CI fixes must receive fresh successful runs before the prerelease is called ready.
