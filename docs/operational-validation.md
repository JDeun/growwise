# Operational completion checklist

This document covers the remaining GrowWise Definition-of-Done checks that cannot be truthfully
completed from repository CI alone. Do not mark the corresponding roadmap items complete until the
real device, credential, or long-lived signing-key work below has actually been performed.

## 1. Local model latency and quality

Run on each representative machine with the intended GrowWise model provider configured:

```bash
uv sync --locked --extra dev
uv run python scripts/benchmark_model.py > benchmark-model.json
```

The report records average and p95 generation latency, whether the LLM path was actually used, and
per-material output size/mode across representative reading, English, math, science, writing, and
field-trip prompts.

Acceptance procedure:

1. Confirm `provider` is `configured` and `llm_used_ratio` is non-zero. A `core-only` report is only
   the deterministic fallback baseline and does not close the local-model benchmark item.
2. Run the same model/configuration more than once after a warm-up run so model load time is not
   confused with steady-state generation latency.
3. Review generated material manually for useful structure and Parent Review suitability; the
   harness intentionally provides only a lightweight automated quality proxy.
4. Record the model name/quantization, machine class, RAM/VRAM, operating system, and measured
   latency in release notes or a separate non-personal benchmark report.
5. Do not commit machine usernames, home paths, device serials, child data, or private model/API
   credentials.

## 2. Minimum and recommended hardware

Run on representative Windows and macOS machines:

```bash
uv sync --locked --extra dev
uv run python scripts/benchmark_hardware.py > benchmark-hardware.json
```

The harness records CPU count, visible RAM, deterministic Core generation throughput, and the current
8 GB minimum / 16 GB recommended memory tier classification.

Acceptance procedure:

1. Test at least one machine near the minimum tier and one at or above the recommended tier.
2. Verify normal Core-only CRUD/search/material workflows, packaged sidecar startup, and UI
   responsiveness on those machines; the synthetic throughput number alone is insufficient.
3. For local-model recommendations, combine this report with the model benchmark because RAM alone
   does not establish model usability.
4. Publish only generalized hardware classes and benchmark values, not personally identifying device
   metadata.

## 3. Production code signing and notarization

The workflow and preflight are already implemented; production trust requires credentials owned by
the release operator. Configure the secrets listed in `docs/release.md`, then create a stable
`vX.Y.Z` tag only after normal CI and the three-platform Desktop Package workflow are green.

Required operational proof before checking the roadmap item:

- macOS stable package is signed with a Developer ID Application identity and notarization succeeds.
- Windows stable NSIS installer is Authenticode-signed with the configured production certificate and
  timestamping succeeds.
- the stable GitHub Release contains the expected signed installers from the same tag/version.
- downloaded installers are smoke-tested on a clean supported Windows machine and on both supported
  macOS architectures where practical.

Never commit certificate files, certificate passwords, Apple credentials, or other signing secrets.

## 4. Tauri updater activation

Tauri updater artifact verification is mandatory and cannot be disabled. Activation therefore waits
for a long-lived updater signing keypair. The Tauri 2 updater documentation is the authoritative
reference: `https://v2.tauri.app/plugin/updater/`.

When the release operator is ready:

```bash
cd desktop
npm run tauri signer generate -- -w ~/.tauri/growwise-updater.key
```

Then:

1. Back up the private key and its password in durable secret storage outside the repository. Losing
   this key prevents publishing trusted updates to already-installed clients.
2. Commit only the public key deliberately in Tauri updater configuration.
3. Add/enable `tauri-plugin-updater`, HTTPS update endpoints, and
   `bundle.createUpdaterArtifacts: true`.
4. Store the private signing key/password in the release secret store used by GitHub Actions.
5. Extend the release workflow to publish the generated updater bundle signatures and update JSON.
6. Test no-update, valid-update, bad-signature, interrupted-download, and rollback/recovery behavior
   on packaged Windows and macOS clients before checking the roadmap item.

Do not generate a disposable key merely to make CI green. The first public updater key is part of the
installed application's long-term trust root.

## Completion rule

Repository CI can verify harnesses, packaging code, safety checks, and unsigned/ad-hoc validation
artifacts. The four roadmap items above move to complete only when their real operational evidence
exists. Keep personal household dogfooding data and release secrets outside the public repository.
