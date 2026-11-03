# Release readiness

The current public scope is an unsigned GitHub prerelease (`0.1.0-alpha.0`) and source.
The [792c283 package workflow](https://github.com/JDeun/growwise/actions/runs/41666654868) passed for
Windows x64, macOS Apple Silicon and macOS Intel with reviewed Python3.12.16/build20261026. Its
production inputs remain unchanged; [downloaded-artifact and actual Core checks](knowledge/experiments/package-three-platform-792c283-20261104.md)
preserve the exact verification scope. [Version5 supported-OS Core/browser and memory validation](knowledge/experiments/supported-os-memory-v5-20261104.md)
also passed. Native Tauri/WebView awaits its final PR run in the
[Native Windows E2E workflow](https://github.com/JDeun/growwise/actions/workflows/native-e2e.yml),
and **no GitHub Release has been published**.

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

The historical Windows loader/package failures are resolved by the successful three-platform runs.
The supported Windows/macOS version5 memory runs passed; older Linux-flatness failures are retained as
historical evidence, not an outstanding release gate for those shipped platforms. Browser-adapter
validation does not replace the pending native WebView result. Later operator-owned evidence includes production signing/notarization on a real stable
release, updater trust-root activation and packaged-client update testing, representative model and
hardware measurements, and household dogfooding. See `docs/operator-handoff.md` for the exact handoff.


Recorded completed runs include Python CI2364passed/1optional denylist skip and frontend303tests.
Those counts are historical execution records, not a newly rerun aggregate for this documentation
update. Two Rust upstream warnings remain on Linux-only dependency paths (`glib0.18.5` and
`proc-macro-error1.0.4`), outside the shipped Windows/macOS closures. The complete cross-target graph is
not described as universally warning-free, secure or commercially certified.

## Current release gate (updated 2026-11-04)

The repository remains on `0.1.0-alpha.0`; its updater overlay is intentionally disabled until an
operator supplies a durable public trust root. The user authorized unsigned prerelease installers
and source; absent certificates or updater activation do not block that initial scope. They remain
requirements for a later signed stable release. No production private key was generated to make
validation green. Three-platform package and supported-OS version5 live/memory verification have
passed. The pending native Windows execution and final PR checks still need their actual outcomes
before the prerelease is called ready; publication has not occurred. See
[the dated readiness assessment](release-readiness-20261103.md) for current evidence, historical links
and the limits on physical-device, educational and stable-update claims.
