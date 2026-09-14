# Desktop release

GrowWise desktop releases are built by `.github/workflows/package.yml` for:

- Windows x64: NSIS installer (`.exe`)
- macOS Apple Silicon: DMG (`.dmg`)
- macOS Intel: DMG (`.dmg`)

The workflow always builds the platform-local Python Core sidecar first, runs a real `/health` smoke test with LLM and embedding features disabled, then bundles that exact executable into the Tauri application resources.

## Pull request packaging

Changes to desktop, Core, packaging configuration, or dependency locks trigger the packaging workflow on pull requests. The generated installers are uploaded as short-lived GitHub Actions artifacts. This is the release-path integration test and does not publish a GitHub Release.

## Tagged release

1. Update the desktop version in all version-bearing manifests before release.
2. Merge only after normal CI and the Desktop Package workflow are green.
3. Create and push a tag matching the Tauri version exactly, for example `v0.1.0-alpha.0`.
4. The packaging workflow builds all three desktop artifacts.
5. After every package job succeeds, the workflow creates or updates the matching GitHub Release and uploads the installers. Tags containing `-` are marked as prereleases.

A mismatched tag and `desktop/src-tauri/tauri.conf.json` version fails before bundling.

## macOS signing and notarization

The repository defaults to Tauri ad-hoc signing (`signingIdentity: "-"`) so CI can validate Apple Silicon/Intel DMGs without repository secrets. Ad-hoc signing is a build-validation fallback, not the final trust model for public distribution.

For a production macOS release, configure the Apple signing/notarization secrets documented by Tauri in the repository Actions secrets. `APPLE_SIGNING_IDENTITY` overrides the default ad-hoc identity. A Developer ID Application release must also be notarized before it is treated as a normal downloaded application by macOS.

Required production credentials depend on the notarization method. Keep certificate material and Apple credentials only in GitHub Actions secrets; never commit them to the repository.

## Windows signing

Unsigned NSIS installers are useful for package-path validation but will produce Windows trust warnings. Before a public stable release, configure Authenticode signing using a protected code-signing certificate or signing service. Keep private keys and credentials outside the repository.

## Local package check

From the repository root, install Python 3.12+, Node.js 22+, Rust stable, and the locked project dependencies. Then:

```bash
python -m pip install "uv==0.12.13"
uv sync --locked --extra desktop-build
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
