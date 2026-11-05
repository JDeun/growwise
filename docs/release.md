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
available for both macOS and Windows. Stable preflight also requires activated updater configuration, its committed native Cargo feature,
a valid public key and the long-lived Tauri updater private signing key. A stable build with updater
artifacts disabled is rejected.

## Stable release overlay

`desktop/src-tauri/tauri.release.conf.json` is merged only into stable tagged builds. It is committed
with updater artifacts disabled so normal development and prerelease packaging do not depend on an
updater trust root.

After the operator creates and safely backs up the long-lived updater signing key,
`desktop/scripts/configure_updater.py` changes that overlay to enable updater artifacts and `build.features=["updater"]`. The optional
plugin, native IPC commands and Settings UI are already committed. The script runs
`cargo check --locked --features updater`; failure restores the previous overlay. It does not create
a key or modify Rust source/lockfiles during activation.

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

The preflight also validates the stable release overlay. Stable tags require `bundle.createUpdaterArtifacts=true`, the native updater build feature, a
Tauri/minisign public key and at least one credential-free HTTPS endpoint. TLS bypasses and downgrades
are rejected; `requireSignedVersion=true` binds the announced version to the signed artifact.
Stable packaging requires `TAURI_SIGNING_PRIVATE_KEY`; zero or partial signed updater sets cannot
publish a stable release. Tauri CLI2.12+ is required and the locked CLI version is checked.
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` is optional when the updater key was created without a password.

## Local package check

Run from the repository root with Node.js22/npm11.6.2, Rust1.98.1 and Python3.12.16 or a newer
supported security-patched Python available. Use a fresh private interpreter/build environment;
shared development environments are deliberately rejected. The installer reads the authoritative
version, build, official catalog URL and SHA from
`assets/licenses/python-standalone/provenance.json`. It verifies the catalog bytes and lets uv
verify the archive checksum. `--no-bin --no-registry` keeps the managed installation from changing
host Python shortcuts or Windows registry entries.

macOS/Linux, using **Bash**:

```bash
set -euo pipefail
growwise_package_dir="$(mktemp -d "${TMPDIR:-/tmp}/growwise-package.XXXXXX")"
export UV_PYTHON_INSTALL_DIR="$growwise_package_dir/python"
export UV_PROJECT_ENVIRONMENT="$growwise_package_dir/venv"
python3 -m pip install "uv==0.12.13"
python3 desktop/scripts/install_packaging_python.py
growwise_package_python="$(python3 desktop/scripts/install_packaging_python.py --print-version)"
uv sync --locked --no-dev --extra desktop-build --managed-python --python "$growwise_package_python"
rustup toolchain install 1.98.1 --profile minimal
cargo fetch --locked --manifest-path desktop/src-tauri/Cargo.toml
npm ci --prefix desktop --no-audit --no-fund
python3 desktop/scripts/check_release_readiness.py
uv run --locked --no-dev --extra desktop-build --managed-python --python "$growwise_package_python" python desktop/scripts/build_core_sidecar.py
uv run --locked --no-dev --extra desktop-build --managed-python --python "$growwise_package_python" python desktop/scripts/build_license_bundle.py --check
uv run --locked --no-dev --extra desktop-build --managed-python --python "$growwise_package_python" python desktop/scripts/smoke_core_sidecar.py
cd desktop
npm run tauri -- icon ../assets/brand/growwise-symbol.svg
npm run tauri -- build --bundles dmg
```

The final DMG command is for macOS; Linux CI validates the frozen Core without a desktop installer.

Windows, using **PowerShell7.4+**:

```powershell
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$growwisePackageDir = Join-Path $env:TEMP ('growwise-package-' + [guid]::NewGuid().ToString('N'))
$env:UV_PYTHON_INSTALL_DIR = Join-Path $growwisePackageDir 'python'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $growwisePackageDir 'venv'
python -m pip install "uv==0.12.13"
python desktop/scripts/install_packaging_python.py
$growwisePackagePython = python desktop/scripts/install_packaging_python.py --print-version
uv sync --locked --no-dev --extra desktop-build --managed-python --python $growwisePackagePython
rustup toolchain install 1.98.1 --profile minimal
cargo fetch --locked --manifest-path desktop/src-tauri/Cargo.toml
npm ci --prefix desktop --no-audit --no-fund
python desktop/scripts/check_release_readiness.py
uv run --locked --no-dev --extra desktop-build --managed-python --python $growwisePackagePython python desktop/scripts/build_core_sidecar.py
uv run --locked --no-dev --extra desktop-build --managed-python --python $growwisePackagePython python desktop/scripts/build_license_bundle.py --check
uv run --locked --no-dev --extra desktop-build --managed-python --python $growwisePackagePython python desktop/scripts/smoke_core_sidecar.py
Push-Location desktop
npm run tauri -- icon ../assets/brand/growwise-symbol.svg
npm run tauri -- build --bundles nsis
Pop-Location
```

Node packages and Cargo source must be installed **before** building Core because its bundled
attribution resource includes the production frontend/native dependency graph. Every uv run keeps
the locked `desktop-build` extra; an implicit sync must not remove PyInstaller before the build.
These ordinary validation packages do not require a signing key or activate automatic updates.
For a later stable build with credentials prepared, add
`--config src-tauri/tauri.release.conf.json` to the Tauri build command. The packaged Core smoke
verifies authenticated startup and a real synthetic PNG-to-JPEG thumbnail without an LLM provider.

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
- enables the committed optional `updater` Cargo feature in the release overlay, and
- runs `cargo check --locked --features updater`, rolling the overlay back if compilation fails.

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


## Installed application update flow

Settings → **앱 업데이트** shows the installed version and whether this build has an activated trust
root. **새 버전 확인** queries only the compiled release endpoint. It sends app/platform metadata,
not child records or Core credentials. **다운로드·설치…** requires an explicit confirmation naming
installation and restart. The WebView cannot supply an endpoint, key or installer path.

The native command downloads one package with strict HTTPS, at most5HTTPS redirect hops and a512MiB limit, then
uses the upstream updater to verify its signature and signed app version. Download/signature failure
leaves Core running and performs no install. Only verified bytes reach the serialized Core shutdown/
installation boundary; installation failure restarts the previous Core at its existing data root,
port and token. macOS restarts after install; the Windows installer handles its own restart after
Core is stopped. Model files, records and API credentials are separate from application packages.

PR/preview builds keep updater support unconfigured. Unit fixtures cover unconfigured/no-update/
available states, native IPC and escaped release notes. Upstream public signature vectors and local
interrupted/oversized/redirect fixtures verify rejection paths without generating a private key or
installing test packages. These checks do not replace a signed end-to-end update on packaged clients.

Every package job compiles the updater feature even when building an unsigned validation installer.
Stable jobs additionally verify macOS codesign/Gatekeeper/stapled notarization and Windows
Authenticode/timestamp after building. The packaged Core smoke uploads a synthetic PNG and requests
a JPEG thumbnail, exercising frozen Pillow plugins as well as authenticated startup/parent-watchdog
imports. Source-level tests alone are not claimed as a packaged-platform runtime pass.

## Tagged release retries and immutable published assets

Release tags must not use the PR concurrency policy. The Desktop Package workflow
automatically cancels older **pull-request** runs for the same ref, but a tag
publication must finish unless it is explicitly cancelled by an operator or GitHub.

A release rerun is **non-destructive**:

- The publishing job requests the release's existing asset metadata first.
- Each existing asset must match the freshly produced asset's **SHA-256**
  (assets[].digest from GitHub Releases versus a local sha256sum).
- Matching assets are kept unchanged. Any mismatched or missing digest **fails
  closed**; the workflow does not delete, replace or overwrite the file.
- Only missing release assets are uploaded. Do not add --clobber to the
  normal publishing path. A deliberate replacement requires an independent
  operator review of provenance and checksums.

**Historical 0.1.0-alpha.0:** the tag-triggered Desktop Package run
[#41689142245](https://github.com/JDeun/growwise/actions/runs/41689142245)
was cancelled on 2026-11-03. Its Linux SBOM steps succeeded, while platform
packaging was cancelled before meaningful build steps. The GitHub Actions API
does not identify the cancellation initiator in this record. This is **not**
evidence of a compiler or test failure. The published installers were instead
promoted from the fully successful three-platform run
[#41685029489](https://github.com/JDeun/growwise/actions/runs/41685029489).
On 2026-11-05 the three published installer GitHub release-asset SHA-256
digests and the source SBOM digest were compared with the bytes extracted from
that verified run's artifact ZIPs; all four values matched.

The cancelled historical run remains cancelled. This retry protection only
affects workflow definitions included in **future** tags; do not move an
existing release tag or overwrite its assets to make an old run green.
