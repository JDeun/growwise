# Release preflight script

`check_release_readiness.py` is dependency-free and runs with Python 3.12+.

It always checks that the Desktop npm, Cargo, and Tauri versions match. It also validates the stable
release overlay in `desktop/src-tauri/tauri.release.conf.json`. When `--tag` is supplied, it verifies
that the tag is exactly `v<desktop-version>`.

Prerelease versions (versions containing `-`) intentionally do not require production signing
credentials. Stable versions require the platform-specific environment documented in
`docs/release.md`.

If the stable release overlay has `bundle.createUpdaterArtifacts=true`, preflight additionally
requires a non-empty updater public key, absolute HTTPS updater endpoints, and
`TAURI_SIGNING_PRIVATE_KEY` for a stable tagged build. The updater private-key password is optional.

Examples:

```bash
python desktop/scripts/check_release_readiness.py
python desktop/scripts/check_release_readiness.py --tag v0.1.0-alpha.0 --platform macos
python desktop/scripts/check_release_readiness.py --tag v0.1.0-alpha.0 --platform windows
```

Updater activation itself is performed only after the long-lived private key has been backed up:

```bash
python desktop/scripts/configure_updater.py \
  --public-key-file ~/.tauri/growwise-updater.key.pub
```
