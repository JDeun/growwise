# Desktop release

GrowWise desktop releases are built by `.github/workflows/package.yml` for:

- Windows x64: NSIS installer (`.exe`)
- macOS Apple Silicon: DMG (`.dmg`)
- macOS Intel: DMG (`.dmg`)

The workflow always builds the platform-local Python Core sidecar first, runs a real `/health` smoke test with LLM and embedding features disabled, then bundles that exact executable into the Tauri application resources.

## Pull request packaging

Changes to desktop, Core, packaging configuration, or dependency locks trigger the packaging workflow on pull requests. The generated installers are uploaded as short-lived GitHub Actions artifacts. This is the release-path integration test and does not publish a GitHub Release.

PR and prerelease builds intentionally use macOS ad-hoc signing and unsigned Windows installers so contributors can validate the complete package path without production credentials.

## Tagged release

1. Update the desktop version in all three version-bearing manifests: `desktop/package.json`, `desktop/src-tauri/Cargo.toml`, and `desktop/src-tauri/tauri.conf.json`.
2. Merge only after normal CI and the Desktop Package workflow are green.
3. Create and push a tag matching the desktop version exactly, for example `v0.1.0-alpha.0`.
4. `desktop/scripts/check_release_readiness.py` verifies version parity and the tag before packaging.
5. The packaging workflow builds all three desktop artifacts.
6. After every package job succeeds, the workflow creates or updates the matching GitHub Release and uploads the installers. Tags containing `-` are marked as prereleases.

A stable tag such as `v1.0.0` has a stricter trust boundary than a prerelease tag such as `v1.0.0-beta.1`: stable packaging fails before bundling unless production signing credentials are available for both macOS and Windows.

## macOS signing and notarization

The repository defaults to Tauri ad-hoc signing (`signingIdentity: "-"`) for pull requests and prerelease tags. Ad-hoc signing is a build-validation fallback and does not remove Gatekeeper approval friction for downloaded applications.

Stable tags import a **Developer ID Application** certificate into a temporary CI keychain and let Tauri perform normal macOS signing and notarization. Configure these GitHub Actions secrets before creating a stable tag:

- `APPLE_CERTIFICATE`: base64-encoded exported Developer ID Application `.p12`
- `APPLE_CERTIFICATE_PASSWORD`: export password for the `.p12`
- `KEYCHAIN_PASSWORD`: temporary CI keychain password
- `APPLE_ID`: Apple Developer account email
- `APPLE_PASSWORD`: app-specific Apple password used for notarization
- `APPLE_TEAM_ID`: Apple Developer Team ID

The workflow discovers the imported Developer ID identity instead of storing its fingerprint in the repository. Certificate material and Apple credentials must remain in GitHub Actions secrets.

## Windows signing

Pull requests and prerelease tags continue to produce unsigned NSIS installers for packaging validation. Stable tags require Authenticode credentials and import the certificate only on the ephemeral Windows runner.

Configure these GitHub Actions secrets before creating a stable tag:

- `WINDOWS_CERTIFICATE`: base64-encoded `.pfx` code-signing certificate
- `WINDOWS_CERTIFICATE_PASSWORD`: `.pfx` export password
- `WINDOWS_TIMESTAMP_URL`: timestamp server supplied by the certificate provider

The workflow reads the imported certificate thumbprint at runtime and writes an ephemeral `tauri.windows.conf.json` containing the SHA-256 signing configuration. The certificate, password, and generated platform config are never committed.

If the certificate issuer requires a hardware-backed, cloud, EV, or Azure Artifact Signing flow instead of an importable PFX, replace the Windows import step with the issuer-specific Tauri `signCommand` integration before publishing a stable tag.

## Release preflight

Run the metadata check locally from the repository root:

```bash
python desktop/scripts/check_release_readiness.py
```

A tagged prerelease can be checked without production credentials:

```bash
python desktop/scripts/check_release_readiness.py --tag v0.1.0-alpha.0 --platform macos
python desktop/scripts/check_release_readiness.py --tag v0.1.0-alpha.0 --platform windows
```

For a stable version, `--platform` is mandatory and the same two commands additionally validate the platform-specific production signing environment. Run both platform checks before creating the stable tag; a bare stable `--tag` check intentionally fails rather than reporting an ambiguous success.

## Local package check

From the repository root, install Python 3.12+, Node.js 22+, Rust stable, and the locked project dependencies. Then:

```bash
python -m pip install "uv==0.12.13"
uv sync --locked --extra desktop-build
python desktop/scripts/check_release_readiness.py
cd desktop
npm ci
npm run tauri -- icon ../assets/brand/growwise-symbol.svg
cd ..
uv run python desktop/scripts/build_core_sidecar.py
uv run python desktop/scripts/smoke_core_sidecar.py
```

Build the platform package from `desktop/`:

```bash
# Windows
npm run tauri -- build --bundles nsis

# macOS
npm run tauri -- build --bundles dmg
```

The application is local-first and the packaged Core smoke test explicitly verifies that startup does not require an LLM provider.

## Updater status

Automatic application updates are intentionally not enabled yet. Tauri updater signatures are mandatory, so updater rollout requires a long-lived updater keypair: the public key is compiled into the application and the private key must be kept outside the repository (for example in GitHub Actions secrets). Do not enable updater artifacts until that key has been generated, backed up, and its public half has been committed deliberately.
