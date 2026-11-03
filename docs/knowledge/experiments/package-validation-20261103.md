# Unsigned package validation · 2026-11-03

This records completed checks of `de3cc074ff067f5e37d9e66afd0cb9a82cc68825`.
The [portable JSON artifact](package-validation-20261103.json) preserves workflow links, outcomes,
source hashes, the downloaded DMG hash and explicit limits. Later CI outcomes extend this evidence;
they do not replace its historical results.

## CI observations

| Scope | Result | Actual checks |
| --- | --- | --- |
| [macOS Intel package](https://github.com/JDeun/growwise/actions/runs/41650864548/job/125968326558) | Passed,17m45s | Pinned interpreter, updater feature/guard tests, full attribution verification, fresh Core authentication/thumbnail smoke, DMG build and upload |
| [macOS ARM package](https://github.com/JDeun/growwise/actions/runs/41650864548/job/125968326601) | Passed,11m32s | Same package checks on ARM |
| [Ubuntu frozen Core](https://github.com/JDeun/growwise/actions/runs/41650864491/job/125968325528) | Passed,1m17s | Locked clean build, attribution sources/hash/inventory checks, actual frozen Core startup/authentication and PNG-to-JPEG thumbnail |

The initial packaging failures were retained in CI: the photo smoke harness read the wrong response
envelope, followed by an interpreter-notice guard failure. The corrected harness consumes the real
`record` object. uv0.12.13's default catalog selected3.12.13+20260807, so Python patch version alone
was insufficient. The final jobs install3.12.13+20260623 from official commit-pinned download
metadata and archive checksums into an isolated directory. The license guard remains strict.

## Downloaded ARM installer: actual bundle checks

The coordinator downloaded `growwise-macos-arm64`, mounted its DMG read-only and verified the actual
bundled resources. The research agent independently rehashed the downloaded file and read the
retained successful Core smoke output.

- File: `GrowWise_0.1.0-alpha.0_aarch64.dmg`.
- SHA-256: `36ed9b80da60263a94849361a8573ff89ee04db6c92ce5e88e839aea18df2f3e`.
- `codesign --verify --deep --strict` returned0. This is an **ad-hoc** signature check; it establishes
  neither Developer ID signing nor notarization.
- The bundled `licenses/` passed the real collector's full hash/inventory check with376rows.
- The actual bundled `binaries/growwise-core` passed protocol1handshake, unauthenticated-request
  rejection, core-only health and synthetic1x1PNG-to-bounded-JPEG conversion. AI features were off.
- The read-only volume was detached successfully.

Separate Core-binary and license-manifest hashes were not retained; this evidence does not invent
them or equate a different local build with the downloaded binary. The exact DMG hash anchors the
verified bundle. The two verification scripts match their recorded `de3cc07` source hashes in JSON.

To reproduce, download the ARM artifact from the linked job, check its hash, mount it read-only and
run the signature check. In the matching clean managed build environment, run
`build_license_bundle.py --check --output <bundle>/Contents/Resources/licenses` and
`smoke_core_sidecar.py <bundle>/Contents/Resources/binaries/growwise-core`. The latter supplies its
own temporary synthetic data directory and runtime token, then stops the owned Core.

## Scope that remains separate

Windows package tests previously exposed a missing CommonControls activation manifest on the test
executable. Native Windows GUI initialization separately failed before the journey; its filtered-token
correction awaits actual CI. Neither is closed by these Mac/Linux results.

The separate Linux navigation soak failed to establish its warmup RSS plateau. Successful Linux
packaging and a small thumbnail smoke do not prove sustained application memory stability.

This experiment uses temporary synthetic records. It does not establish household usefulness,
learning gains, physical Windows-device coverage, paid remote-AI/API-key operation or a signed
stable/update trust chain. The current public scope is an unsigned GitHub prerelease and source.

Source registry: `GW-PACKAGE-VALIDATION-OBSERVED-20261103`.
Experiment registry: `EXP-PACKAGE-VALIDATION-OBSERVED-20261103`.
