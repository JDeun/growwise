# Release readiness assessment — 2026-11-03

Updated **2026-11-04**. The agreed scope is **unsigned GitHub prerelease installers and source for
`0.1.0-alpha.0`**. Revision `f733bfc` fixes a real first-photo workflow bug: saving a draft collapsed
the section containing parent confirmation. Draft review and pending progress now keep that section
open. A production-browser regression uses a real pointer to reopen a saved draft; the live harness
also refuses hidden buttons. The [actual Windows native journey](knowledge/experiments/native-windows-gui-20261104.md)
and [Windows/macOS live runs](https://github.com/JDeun/growwise/actions/runs/41685029397) passed on this
correction. [General CI](https://github.com/JDeun/growwise/actions/runs/41685029503) passed all11jobs.
[Fresh installers](https://github.com/JDeun/growwise/actions/runs/41685029489) passed on all three
platforms; earlier installers are not its release artifacts. Publication and downloads are recorded on the
[GitHub prerelease page](https://github.com/JDeun/growwise/releases/tag/v0.1.0-alpha.0).

Platform certificates, notarization and a durable updater signing key are requirements for a later
signed stable release. They do not block the explicitly authorized unsigned prerelease. The updater
truthfully exposes `notconfigured`; no disposable private key was generated to make validation green.
Existing stable-tag signing and trust-root checks remain enforced.

## Completed package and runtime verification

The [792c283 package workflow](https://github.com/JDeun/growwise/actions/runs/41666654868) passed for
Windows x64, macOS Apple Silicon and macOS Intel, including three actual updater security tests per
platform, Core build, authentication/photo smoke, attribution checks and NSIS/DMG upload. The reviewed
runtime is **Python3.12.16 / build20261026**. Its production inputs matched through `661a38a`, whose
[three-platform package run](https://github.com/JDeun/growwise/actions/runs/41679826972) also passed.
The later `f733bfc` frontend correction has its own successful
[three-platform installer and SBOM run](https://github.com/JDeun/growwise/actions/runs/41685029489).

The initial unsigned prerelease promotes those exact `f733bfc` installer artifacts. The final source
tag adds only release/evidence documentation; all846tracked non-documentation files, including README
metadata, product sources, locks and build inputs, match the tested revision. The source SBOM describes
the `f733bfc` snapshot. Published asset bytes are identified by `SHA256SUMS` and build provenance in the
release notes. This is artifact promotion, not a claim that independent rebuilds produce identical bytes.

The [three-platform record](knowledge/experiments/package-three-platform-792c283-20261104.md) preserves
all downloaded installer sizes and SHA-256 values. Windows has374aggregate attribution rows, ARM376
and Intel377; these include multiple ecosystems, not just Python packages. Both downloaded DMGs passed
read-only deep/strict ad-hoc signature and bundled-license checks. The downloaded ARM app's actual
Core also passed local authentication and PNG-to-JPEG smoke. Windows and Intel Core execution was
observed on their actual CI hosts; their installers were not executed locally on the ARM computer.

Earlier [Python3.12.13 package observations](knowledge/experiments/package-validation-20261103.md)
remain historical. Their release-security suitability was superseded by the
[official ZIP/TLS/XML review](knowledge/experiments/python-runtime-security-20261103.md). Source
installation now requires Python>=3.12.16. This minimum does not certify every old patch of a higher
Python minor series. The previous Windows test-loader and Cargo-output decoding failures are resolved
by the successful package runs; they are not outstanding release blockers.

## Supported-OS workflow and memory evidence

[Version5 actual Core/browser validation](knowledge/experiments/supported-os-memory-v5-20261104.md)
passed on Windows x64 and Intel macOS CI and separately on local ARM macOS. Every run completed
22assertions against the authenticated real Core, including child isolation, restore, conversations,
original photos/thumbnails, selected export, real PDF output and infant parent-guide printing. The
repeated print check counts twice; these are assertion counts, not22independent features.

Each run exercised a fixed1000-record workload and the entire requested120-second measured interval
after representative navigation warmup. All sampled Core RSS/browser-heap changes stayed within the
unchanged +32MiB/+8MiB budgets. Windows additionally measured private bytes for the verified actual
server, not its small venv launcher, within a separate +32MiB retention budget. The complete cold,
warmup and steady traces and earlier failures are preserved in that record. This is bounded observed
memory behavior, not proof of the absence of every leak.

These runs use the production frontend and an IPC transport adapter. The separate
[successful native Windows journey](knowledge/experiments/native-windows-gui-20261104.md) exercises
the original Rust IPC and verifies the actual managed Core exits. AI was disabled. The earlier
[Linux allocator investigation](knowledge/experiments/linux-core-memory-20261103.md) and
[supported-OS version4 failures](knowledge/experiments/supported-os-live-20261104.md) remain historical
evidence; the old Linux-flatness assumption is not an unresolved gate for the shipped Windows/macOS
scope.

## Audit resolutions and recorded checks

| Finding | Implemented resolution | Evidence scope |
| --- | --- | --- |
| Deleted, edited or revoked source bodies could survive projection cleanup | Current originals, fingerprints and grants replace cached bodies in RAG, evidence reading and derived Wiki | Source-edit/delete/revocation/race regressions |
| Interrupted photos could remain processing | Source/job reconciliation and actionable retry | Recovery regressions and actual photo workflows |
| Gallery loaded24originals and retained large image surfaces | Authenticated bounded JPEG thumbnails, limited preview decoding, cache/concurrency bounds and URL cleanup | Thumbnail/privacy tests and actual browser/packaged-Core PNG checks |
| Overlapping polls could starve completion | Completion-driven serial polling with current-child guards | Polling regressions and actual-Core journeys |
| Development dependencies had36reports across5packages | Compatible locked dependency updates | Recorded pip-audit and npm audits; no universal vulnerability-absence claim |
| limit8 decoded the full corpus | SQL/filter/limit selects only needed payloads | Recorded synthetic10k comparison and bounded decode regressions |
| Embedding changes synchronously reembedded the corpus | One background worker,32-row pages, generation fences and lexical fallback | Worker/model-change regressions |
| Recovery shared limits across job types | Job-specific photo and AI recovery limits | Recovery regressions |

The `f733bfc` Python CI passed **2380tests with1skip on Ubuntu/macOS** and **2378tests with3skips on
Windows**; the frontend passed **304tests**. Coverage was81%. These are completed-run counts, with
platform/optional skips and the third-party warning retained in CI. Production build and lint passed.
Child selection has a single provider with stale
response fences and child-keyed controllers. Updater failure, signature, interrupted-download and
operation-serialization guards are covered by actual test runs, using public/synthetic fixtures rather
than a production updater key.

CodeQL and gitleaks passed on reviewed snapshots. The individually triaged CodeQL test-harness alert
remains bounded to the validated local DevTools transport; no broad query/path suppression was added.
Rust still reports two upstream warnings in **Linux-only** dependency paths: `glib0.18.5` and
`proc-macro-error1.0.4`. They are outside the shipped Windows/macOS dependency closures. This does not
make the complete cross-target Rust graph warning-free or establish universal security.

## Remaining acceptance and operational limits

The native Windows journey completed all six stages with original W3C pointer clicks, including
photo confirmation after the first draft, child isolation and a real backup. Its report records
`core_exited=true` for the verified lock-owner process and no renderer errors. General CI passed all11
jobs, and all three fresh installer jobs plus SBOM passed. The agreed unsigned-prerelease engineering
acceptance is complete; the operational limits below remain distinct.

The [repeated model experiment](knowledge/experiments/model-repeat-quality-20261103.md) retains51actual
calls and distinguishes later saved-response replay from new inference. Its final24-call observed
cohort contains22AI-enhanced outputs and2reviewable fallbacks. This is not teacher/parent acceptance,
measured learning effectiveness, universal factual correctness or child-safety certification.

Physical-device coverage, longitudinal household use, every paid remote-provider account, stable
Developer ID/Authenticode signing, notarization and a production-key packaged-client update chain are
not established by these checks. The unsigned prerelease scope is not a universal commercial-readiness
or security assertion. No household records, personal API keys or signing secrets belong in public
evidence.

See [release gates](RELEASE_READINESS.md), [release operations](release.md),
[operator handoff](operator-handoff.md), [privacy boundaries](privacy-and-safety.md) and
[material quality contract](material-quality-contract.md). Historical append-only evidence remains
unchanged.
