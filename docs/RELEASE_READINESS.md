# Release readiness

The current public scope is an unsigned GitHub prerelease (`0.1.0-alpha.0`) and source.
GrowWise can validate and package Windows and macOS installers in CI without production credentials.
Public **stable** distribution has an additional trust boundary enforced by
`.github/workflows/package.yml`.

## Repository-complete

- Version parity is checked across `desktop/package.json`, `desktop/src-tauri/Cargo.toml`, and
  `desktop/src-tauri/tauri.conf.json`.
- A release tag must match the desktop version exactly.
- Pull requests and prerelease tags build and smoke-test Windows x64, macOS Apple Silicon, and macOS
  Intel installers.
- The desktop frontend job runs lint/tests/production build and uploads `growwise-frontend-dist` so
  visual QA can inspect the exact production Vite bundle rather than a hand-built mock.
- The current product shell and all nine workspaces have production-bundle visual acceptance coverage
  for page errors, horizontal overflow, and visible text/button clipping.

- Stable tags refuse to package unless platform signing credentials are present.
- Stable macOS builds import a Developer ID Application certificate and provide notarization
  credentials to Tauri.
- Stable Windows builds import a PFX certificate and generate the Tauri signing config from its
  runtime thumbprint.
- `desktop/src-tauri/tauri.release.conf.json` isolates updater artifacts to stable releases.
- `desktop/scripts/configure_updater.py` converts a backed-up updater public key into the required
  release overlay/build feature and validates committed native wiring with `cargo check --locked
  --features updater`; optional native commands and Settings controls are already present.
- Stable preflight validates updater public configuration and requires an activated trust root and private updater signing
  key for every stable tag. Disabled updater configurations cannot pass stable preflight.
- `desktop/scripts/prepare_release_assets.py` normalizes three-platform artifacts and generates the
  Tauri static `latest.json` only when a complete signed updater set is present.
- The release workflow publishes installers, updater bundles/signatures, and `latest.json` from the
  same stable tag once updater trust-root activation has been performed.

## Operator-only credentials before the first stable tag

These values cannot and must not be committed to the repository.

### macOS

Configure GitHub Actions secrets:

- `APPLE_CERTIFICATE`
- `APPLE_CERTIFICATE_PASSWORD`
- `KEYCHAIN_PASSWORD`
- `APPLE_ID`
- `APPLE_PASSWORD`
- `APPLE_TEAM_ID`

### Windows

Configure GitHub Actions secrets:

- `WINDOWS_CERTIFICATE`
- `WINDOWS_CERTIFICATE_PASSWORD`
- `WINDOWS_TIMESTAMP_URL`

If the Windows certificate provider requires a cloud/hardware signing command instead of an
importable PFX, the release operator must select that provider and replace the importable-PFX step
with its provider-specific Tauri `signCommand` integration before the first stable release.

## Updater trust root

The repository-side updater implementation is prepared, but the updater remains disabled in the
committed stable overlay until a **long-lived** signing keypair is deliberately generated and backed
up. The first public key becomes part of installed clients' trust root, so this step cannot be
truthfully automated with a disposable CI key.

After durable secret storage is ready, the operator runs:

```bash
cd desktop
npm run tauri signer generate -- -w ~/.tauri/growwise-updater.key
cd ..
python desktop/scripts/configure_updater.py \
  --public-key-file ~/.tauri/growwise-updater.key.pub
```

Review and commit only the generated public/code changes, then configure GitHub Actions secrets:

- `TAURI_SIGNING_PRIVATE_KEY`
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` when applicable

The stable workflow then handles updater artifact signing, three-platform asset collection, static
`latest.json` generation, and GitHub Release upload automatically.

The [contract trace](FEATURE_TRACE_AUDIT.md) closes the original nine missing behaviors and tracks
later findings separately. Selective child/date raw-record export is implemented and regression-tested;
its [actual production UI ZIP-saving check](knowledge/experiments/live-core-browser-20261103-verified.md) now passes, including scope/hash checks and rejection by full restore. Infant parent-guide print and worksheet exclusion also pass. The bounded contract trace has no remaining confirmed implementation gap; this does not assert universal absence of defects.

Build, package, Windows execution and Linux memory-regression failures remain repository work until
their corrected CI runs pass. Later operator-owned evidence includes production signing/notarization on a real stable
release, updater trust-root activation and packaged-client update testing, representative model and
hardware measurements, and household dogfooding. See `docs/operator-handoff.md` for the exact handoff.


## Current release gate (2026-11-03)

The repository remains on `0.1.0-alpha.0`; its updater overlay is intentionally disabled until an
operator supplies a durable public trust root. The user authorized unsigned prerelease installers
and source; absent certificates or updater activation do not block that initial scope. They remain
requirements for a later signed stable release. No production private key was generated to make
validation green. Corrected package/native-Windows/Linux-soak CI still needs to pass before the
prerelease is called ready. See [the dated readiness assessment](release-readiness-20261103.md) for audit
resolutions, evidence scope and outstanding physical Windows/signed-update verification.
