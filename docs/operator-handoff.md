# Operator-only completion handoff

GrowWise repository work is intended to stop at the boundary where a real person, real device, or
long-lived secret is required. The repository must not fabricate those inputs or commit them.

Everything below is therefore **operator-only**. Code changes, validation harnesses, packaging
workflows, updater asset generation, and safety checks are already automated in the repository.

## 1. Household dogfooding

Use the packaged application in normal household use and verify that the parent-led infant flow,
records, search, materials, Parent Review, backup/restore, and long-term growth context remain useful.
Do not commit household child data or private observations as evidence.

## 2. Local-model latency and quality evidence

On each representative machine with the intended local model configured:

```bash
uv sync --locked --extra dev
uv run python scripts/benchmark_model.py --warmup-rounds 1 --repeats 3 > benchmark-model.json
```

Review every generated sample as well as the latency fields. Record only generalized machine/model
information in public release evidence.

## 3. Minimum/recommended hardware evidence

Run on at least one machine near the documented minimum tier and one at or above the recommended
tier, including representative Windows and macOS hardware:

```bash
uv sync --locked --extra dev
uv run python scripts/benchmark_hardware.py > benchmark-hardware.json
```

Also verify packaged sidecar startup, normal CRUD/search/material flows, and UI responsiveness. CI
runner measurements are regression evidence, not a substitute for representative-device testing.

## 4. Production signing and first stable release

Obtain and configure the production credentials listed in `docs/release.md`:

- Apple Developer ID Application certificate + notarization credentials
- Windows production code-signing certificate + timestamp service

Store them only as GitHub Actions secrets. Then create a stable `vX.Y.Z` tag and verify that the
published macOS packages are signed/notarized and the Windows installer is Authenticode-signed and
timestamped. Smoke-test downloaded installers on clean supported systems.

The repository preflight intentionally blocks a stable release when required credentials are absent.

## 5. Long-lived updater trust root

Tauri updater signatures cannot be disabled, and the first updater public key becomes part of the
installed application's long-term trust root. Generate this key only when durable private-key backup
is available:

```bash
cd desktop
npm run tauri signer generate -- -w ~/.tauri/growwise-updater.key
cd ..
```

Back up the private key and password outside the repository. Then run the repository configurator
with the generated **public** key:

```bash
python desktop/scripts/configure_updater.py \
  --public-key-file ~/.tauri/growwise-updater.key.pub
```

The configurator prepares the release-only Tauri updater config, adds `tauri-plugin-updater` to the
Rust shell, wires the plugin into the Tauri builder, updates `Cargo.lock` through `cargo check`, and
uses the default GitHub Release endpoint unless `--endpoint` is supplied.

After reviewing and committing those generated public/code files, store these GitHub Actions secrets:

- `TAURI_SIGNING_PRIVATE_KEY`
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` when the key has a password

The stable release workflow is already wired to:

1. build updater artifacts only for stable tags through `tauri.release.conf.json`,
2. sign updater bundles with the private key from Actions secrets,
3. collect Windows x64, macOS arm64, and macOS x64 updater bundles/signatures,
4. generate the static Tauri `latest.json`, and
5. upload the normalized installers, updater bundles, signatures, and manifest to the GitHub Release.

Before marking updater activation complete, test no-update, valid-update, invalid-signature,
interrupted-download, and recovery behavior on packaged Windows and macOS clients.

Never commit the updater private key, password, production signing certificates, Apple credentials,
or household data.
