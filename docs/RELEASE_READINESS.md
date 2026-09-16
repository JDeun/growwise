# Release readiness

GrowWise can validate and package Windows and macOS installers in CI without production credentials. Public **stable** distribution has an additional trust boundary enforced by `.github/workflows/package.yml`.

## Repository-complete

- Version parity is checked across `desktop/package.json`, `desktop/src-tauri/Cargo.toml`, and `desktop/src-tauri/tauri.conf.json`.
- A release tag must match the desktop version exactly.
- Pull requests and prerelease tags build and smoke-test Windows x64, macOS Apple Silicon, and macOS Intel installers.
- Stable tags refuse to package unless platform signing credentials are present.
- Stable macOS builds import a Developer ID Application certificate and provide notarization credentials to Tauri.
- Stable Windows builds import a PFX certificate and generate the Tauri signing config from its runtime thumbprint.

## External credentials still required before the first stable tag

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

If the Windows certificate provider requires a cloud/hardware signing command instead of an importable PFX, adapt the workflow to the provider-specific Tauri `signCommand` before a stable release.

## Automatic updater

The updater remains deliberately disabled until a long-lived Tauri updater signing keypair is generated and backed up. The public key may be committed to application configuration; the private key must remain outside the repository. Losing the updater private key prevents shipping trusted updates to existing installations, so it should not be generated as an incidental CI artifact.
