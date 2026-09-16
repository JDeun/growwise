# Desktop release

GrowWise desktop releases are built by `.github/workflows/package.yml` for:

- Windows x64: NSIS installer (`.exe`)
- macOS Apple Silicon: DMG (`.dmg`)
- macOS Intel: DMG (`.dmg`)

The workflow always builds the platform-local Python Core sidecar first, runs a real `/health` smoke
test with LLM and embedding features disabled, then bundles that exact executable into the Tauri
application resources.

## Pull request packaging

Changes to desktop, Core, packaging configuration, or dependency locks trigger the packaging workflow
on pull requests. The generated installers are uploaded as short-lived GitHub Actions artifacts. This
is the release-path integration test and does not publish a GitHub Release.

PR and prerelease builds intentionally use macOS ad-hoc signing and unsigned Windows installers so
contributors can validate the complete package path without production credentials. They do not use
the stable-only `tauri.release.conf.json` overlay, so updater signing keys are never required for PR
validation.

## Tagged release

1. Update the desktop version in all three version-bearing manifests: `desktop/package.json`,
   `desktop/src-tauri/Cargo.toml`, and `desktop/src-tauri/tauri.conf.json`.
2. Merge only after normal CI and the Desktop Package workflow are green.
3. Create and push a tag matching the desktop version exactly, for example `v0.1.0-alpha.0`.
4. `desktop/scripts/check_release_readiness.py` verifies version parity and the tag before packaging.
5. The packaging workflow builds all three desktop artifacts.
6. After every package job succeeds, `desktop/scripts/prepare_release_assets.py` normalizes the
   downloaded platform artifacts and, when signed updater bundles exist, emits Tauri `latest.json`.
7. The workflow creates or updates the matching GitHub Release and uploads the normalized assets.
   Tags containing `-` are marked as prereleases.

A stable tag such as `v1.0.0` has a stricter trust boundary than a prerelease tag such as
`v1.0.0-beta.1`: stable packaging fails before bundling unless production signing credentials are
available for both macOS and Windows. If the updater release overlay is activated, the stable
preflight also requires the long-lived Tauri updater private key.

## Stable release overlay

`desktop/src-tauri/tauri.release.conf.json` is merged only into stable tagged builds. It is committed
with updater artifacts disabled so normal development and prerelease packaging do not depend on an
updater trust root.

After the operator creates and safely backs up the long-lived updater signing key,
`desktop/scripts/configure_updater.py` changes that overlay to enable updater artifacts and adds the
updater plugin to the Rust shell. The script also runs `cargo check`, which refreshes `Cargo.lock` and
validates the generated Rust dependency wiring.

## macOS signing and notarization

The repository defaults to Tauri ad-hoc signing (`signingIdentity: "-"`) for pull requests and
prerelease tags. Ad-hoc signing is a build-validation fallback and does not remove Gatekeeper approval
friction for downloaded applications.

Stable tags import a **Developer ID Application** certificate into a temporary CI keychain and let
Tauri perform normal macOS signing and notarization. Configure these GitHub Actions secrets before
creating a stable tag:

- `APPLE_CERTIFICATE`: base64-encoded exported Developer ID Application `.p12`
- `APPLE_CERTIFICATE_PASSWORD`: export password for the `.p12`
- `KEYCHAIN_PASSWORD`: temporary CI keychain password
- `APPLE_ID`: Apple Developer account email
- `APPLE_PASSWORD`: app-specific Apple password used for notarization
- `APPLE_TEAM_ID`: Apple Developer Team ID

The workflow discovers the imported Developer ID identity instead of storing its fingerprint in the
repository. Certificate material and Apple credentials must remain in GitHub Actions secrets.

## Windows signing

Pull requests and prerelease tags continue to produce unsigned NSIS installers for packaging
validation. Stable tags require Authenticode credentials and import the certificate only on the
ephemeral Windows runner.

Configure these GitHub Actions secrets before creating a stable tag:

- `WINDOWS_CERTIFICATE`: base64-encoded `.pfx` code-signing certificate
- `WINDOWS_CERTIFICATE_PASSWORD`: `.pfx` export password
- `WINDOWS_TIMESTAMP_URL`: timestamp server supplied by the certificate provider

The workflow reads the imported certificate thumbprint at runtime and writes an ephemeral
`tauri.windows.conf.json` containing the SHA-256 signing configuration. The certificate, password,
and generated platform config are never committed.

If the certificate issuer requires a hardware-backed, cloud, EV, or Azure Artifact Signing flow
instead of an importable PFX, replace the Windows import step with the issuer-specific Tauri
`signCommand` integration before publishing a stable tag.

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

For a stable version, `--platform` is mandatory and the same two commands additionally validate the
platform-specific production signing environment. Run both platform checks before creating the stable
tag; a bare stable `--tag` check intentionally fails rather than reporting an ambiguous success.

The preflight also validates the stable release overlay. When
`bundle.createUpdaterArtifacts=true`, the overlay must contain a non-empty updater public key and at
least one absolute HTTPS endpoint, and stable packaging requires `TAURI_SIGNING_PRIVATE_KEY`.
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` is optional when the updater key was created without a password.

## Local package check

From the repository root, install Python 3.12+, Node.js 22+, Rust stable, and the locked project
dependencies. Then:

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

Build the ordinary validation package from `desktop/`:

```bash
# Windows
npm run tauri -- build --bundles nsis

# macOS
npm run tauri -- build --bundles dmg
```

To reproduce the stable overlay locally after signing credentials are available, append:

```bash
--config src-tauri/tauri.release.conf.json
```

The application is local-first and the packaged Core smoke test explicitly verifies that startup
does not require an LLM provider.

## Updater activation

Tauri updater signatures are mandatory. The first public updater key is compiled into the installed
application and therefore becomes a long-lived trust root. Do not generate a disposable key merely
to make CI green.

The code-side activation path is automated. Once durable private-key backup is ready:

```bash
cd desktop
npm run tauri signer generate -- -w ~/.tauri/growwise-updater.key
cd ..
python desktop/scripts/configure_updater.py \
  --public-key-file ~/.tauri/growwise-updater.key.pub
```

The configurator:

- enables `bundle.createUpdaterArtifacts` only in `tauri.release.conf.json`,
- writes the public key and HTTPS update endpoint,
- adds `tauri-plugin-updater = "2"` to the Rust dependencies,
- wires the updater plugin into the Tauri builder, and
- runs `cargo check` so `Cargo.lock` and Rust wiring are updated together.

The default endpoint is:

```text
https://github.com/JDeun/growwise/releases/latest/download/latest.json
```

Use `--endpoint` only when a different HTTPS update service is intentionally chosen.

After committing the generated public/code files, configure these GitHub Actions secrets:

- `TAURI_SIGNING_PRIVATE_KEY`
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` when applicable

Stable packaging then automatically uploads the updater bundles and `.sig` files for Windows x64,
macOS arm64, and macOS x64. The release job generates a static `latest.json` whose platform URLs point
to the normalized assets in that same GitHub Release.

The remaining updater work is operational trust validation on packaged clients; see
`docs/operator-handoff.md` and `docs/operational-validation.md`.
