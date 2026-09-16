# Operational completion checklist

This document covers the remaining GrowWise Definition-of-Done checks that cannot be truthfully
completed from repository CI alone. Do not mark the corresponding roadmap items complete until the
real device, credential, or long-lived signing-key work below has actually been performed.

All repository-side harnesses and release automation are expected to be complete before these steps.
A compact operator handoff is also available in `docs/operator-handoff.md`.

## 1. Local model latency and quality

Run on each representative machine with the intended GrowWise model provider configured. The
recommended evidence run performs one untimed warm-up round and three measured rounds:

```bash
uv sync --locked --extra dev
uv run python scripts/benchmark_model.py --warmup-rounds 1 --repeats 3 > benchmark-model.json
```

The report records the configured provider kind/model ID, stage, warm-up/measured round counts,
average and p95 generation latency, generator-mode counts, whether the LLM path was actually used,
and the exact synthetic generated title/Markdown for every measured sample. The synthetic output is
included so a reviewer can inspect the same artifacts that produced the timing/fallback evidence;
it contains no household child data.

If LLM features are enabled, provider construction uses the same `Settings` +
`create_model_provider` path as the application; invalid provider configuration is not silently
converted into a Core-only benchmark.

Acceptance procedure:

1. Confirm `provider` is `configured`, `llm_used_ratio` is non-zero, and inspect
   `generator_mode_counts`. A `core-only` report is only the deterministic fallback baseline and does
   not close the local-model benchmark item.
2. Use at least one warm-up round and multiple measured repeats so model load time is not confused
   with steady-state generation latency. Keep the exact command/round counts with the result.
3. Review every measured `title` + `content_markdown` sample for useful structure, age/stage fit,
   scaffold quality, obvious factual problems, and Parent Review suitability. Automated mode/count
   fields are not a substitute for this review.
4. Record the model name/quantization, machine class, RAM/VRAM, operating system, and measured
   latency in release notes or a separate non-personal benchmark report.
5. Do not commit machine usernames, home paths, device serials, household child data, or private
   model/API credentials.

## 2. Minimum and recommended hardware

Run on representative Windows and macOS machines:

```bash
uv sync --locked --extra dev
uv run python scripts/benchmark_hardware.py > benchmark-hardware.json
```

The harness records operating system, architecture, CPU count, visible physical RAM, deterministic
Core generation throughput, and the current 8 GB minimum / 16 GB recommended memory tier
classification. Windows RAM is read through `GlobalMemoryStatusEx`; macOS RAM is read through
Apple's `hw.memsize` sysctl; other POSIX hosts use the local `sysconf` page-size/page-count interface.

Acceptance procedure:

1. Test at least one machine near the minimum tier and one at or above the recommended tier.
2. Verify normal Core-only CRUD/search/material workflows, packaged sidecar startup, and UI
   responsiveness on those machines; the synthetic throughput number alone is insufficient.
3. For local-model recommendations, combine this report with the model benchmark because RAM alone
   does not establish model usability.
4. Publish only generalized hardware classes and benchmark values, not personally identifying device
   metadata.

GitHub Actions Windows/macOS runners provide cross-platform regression coverage for the harness, but
they are not representative household hardware and therefore do not close this item.

## 3. Production code signing and notarization

The workflow and preflight are implemented. The remaining work requires credentials owned by the
release operator. Configure the secrets listed in `docs/release.md`, then create a stable `vX.Y.Z`
tag only after normal CI and the three-platform Desktop Package workflow are green.

Required operational proof before checking the roadmap item:

- macOS stable package is signed with a Developer ID Application identity and notarization succeeds.
- Windows stable NSIS installer is Authenticode-signed with the configured production certificate and
  timestamping succeeds.
- the stable GitHub Release contains the expected signed installers from the same tag/version.
- downloaded installers are smoke-tested on a clean supported Windows machine and on both supported
  macOS architectures where practical.

Never commit certificate files, certificate passwords, Apple credentials, or other signing secrets.

## 4. Tauri updater trust-root activation

Repository-side updater preparation is automated:

- `desktop/src-tauri/tauri.release.conf.json` isolates updater artifacts to stable builds.
- `desktop/scripts/configure_updater.py` installs/wires the updater plugin from a public key.
- `desktop/scripts/check_release_readiness.py` validates updater configuration and requires the
  private signing key for stable builds when updater artifacts are enabled.
- `.github/workflows/package.yml` collects updater bundles/signatures.
- `desktop/scripts/prepare_release_assets.py` normalizes assets and generates static `latest.json`.

Tauri updater artifact verification is mandatory and cannot be disabled. Activation therefore waits
only for a durable long-lived updater signing keypair owned by the release operator. The Tauri 2
updater documentation remains the authoritative external reference:
`https://v2.tauri.app/plugin/updater/`.

When durable secret backup is available:

```bash
cd desktop
npm run tauri signer generate -- -w ~/.tauri/growwise-updater.key
cd ..
python desktop/scripts/configure_updater.py \
  --public-key-file ~/.tauri/growwise-updater.key.pub
```

Then:

1. Back up the private key and its password in durable secret storage outside the repository. Losing
   this key prevents publishing trusted updates to already-installed clients.
2. Review and commit only the generated public/code changes, including the public updater key,
   updater Rust wiring, refreshed `Cargo.lock`, and release overlay.
3. Store `TAURI_SIGNING_PRIVATE_KEY` and, when applicable,
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` in GitHub Actions secrets.
4. Create a stable release and verify that updater bundles, `.sig` files, and `latest.json` are
   published for Windows x64, macOS arm64, and macOS x64.
5. Test no-update, valid-update, bad-signature, interrupted-download, and recovery behavior on
   packaged Windows and macOS clients before checking the roadmap item.

Do not generate a disposable key merely to make CI green. The first public updater key is part of the
installed application's long-term trust root.

## 5. Household dogfooding

The Phase 1 code path is complete, but real household usefulness cannot be proven by synthetic CI.
Use the packaged app over normal day-to-day use and verify the infant workflow, observations,
activities, search, Parent Review, materials, backup/restore, and long-term growth context. Keep
household records private; public evidence should contain only generalized findings.

## Completion rule

Repository CI can verify implementation, harnesses, packaging code, safety checks, cross-platform
regressions, and unsigned/ad-hoc validation artifacts. The remaining roadmap items move to complete
only when their real operator-owned evidence exists. Keep household dogfooding data and release
secrets outside the public repository.
