# Release readiness

GrowWise can validate and package Windows and macOS installers in CI without production credentials.
Public **stable** distribution has an additional trust boundary enforced by
`.github/workflows/package.yml`.

## Repository-complete

- Version parity is checked across `desktop/package.json`, `desktop/src-tauri/Cargo.toml`, and
  `desktop/src-tauri/tauri.conf.json`.
- A release tag must match the desktop version exactly.
- Pull requests and prerelease tags build and smoke-test Windows x64, macOS Apple Silicon, and macOS
  Intel installers.
- Stable tags refuse to package unless platform signing credentials are present.
- Stable macOS builds import a Developer ID Application certificate and provide notarization
  credentials to Tauri.
- Stable Windows builds import a PFX certificate and generate the Tauri signing config from its
  runtime thumbprint.
- `desktop/src-tauri/tauri.release.conf.json` isolates updater artifacts to stable releases.
- `desktop/scripts/configure_updater.py` converts a backed-up updater public key into the required
  release config and Rust plugin wiring, and validates it with `cargo check`.
- Stable preflight validates updater public configuration and requires the private updater signing
  key when updater artifacts are enabled.
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

The remaining work is operator-owned evidence: production signing/notarization on a real stable
release, updater trust-root activation and packaged-client update testing, representative model and
hardware measurements, and household dogfooding. See `docs/operator-handoff.md` for the exact handoff.
