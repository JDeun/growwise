# Release preflight script

`check_release_readiness.py` is dependency-free and runs with Python 3.12+.

It always checks that the Desktop npm, Cargo, and Tauri versions match. When `--tag` is supplied, it also verifies that the tag is exactly `v<desktop-version>`.

Prerelease versions (versions containing `-`) intentionally do not require production signing credentials. Stable versions require the platform-specific environment documented in `docs/release.md`.

Examples:

```bash
python desktop/scripts/check_release_readiness.py
python desktop/scripts/check_release_readiness.py --tag v0.1.0-alpha.0 --platform macos
python desktop/scripts/check_release_readiness.py --tag v0.1.0-alpha.0 --platform windows
```
