# Release readiness assessment — 2026-11-03

Status: **repository hardening implemented; signed public stable release remains blocked**.
This is a working-tree assessment based on `c452317` plus the current fixes, pending the integration
agent's final frozen-source tests and commit CI. It does not certify an unsigned validation build as
a production release. Earlier observed21-step browser/model artifacts remain unchanged.

## Eight audit findings

| Finding | Implemented resolution | Evidence scope |
| --- | --- | --- |
| 1. Deleted/edited RAG text still entered model prompts after projection failure | `source_snapshot.py`, `SQLiteProjection.get_current_entity`, ChildContextService/GroundedRagService and original reader resolve current Markdown and current raw sharing grants; cached bodies are never model evidence | Research/security lane observed95focused tests including23new deletion/edit/revocation/narrowing/delay/source-tamper/reader/API cases; no remote request or personal data used |
| 2. Photos could remain permanently processing after final interruption | `services/photo_jobs.py` and pending-photo recovery reconcile source status and terminal/interrupted jobs | Integration/photography lane tests; final aggregate evidence pending |
| 3. Gallery loaded24originals, up to480MiB | Bounded metadata-free JPEG thumbnails; native/API/client thumbnail path; separate current-photo original handling and URL cleanup | Photography lane tests and browser; new packaged smoke exercises PNG→JPEG inside frozen binary; final packaged run pending |
| 4. Overlapping1.5s photo polls invalidated generations and starved completion | Completion-driven serial polling with current-child guards | Serial-polling and photo UI regressions; final aggregate evidence pending |
| 5. Python development dependencies had36reports/31unique advisory IDs across5packages; runtime audit0 | Dependency updates and lock refresh owned by dependency lane | Final sanitized dependency audit results must be attached by integration agent; do not interpret old counts as current findings |
| 6. limit8 decoded the full entity corpus | SQL/filter/limit paths avoid decoding every payload before truncation | Integration agent's synthetic10k comparison:142.27ms/67,340,086B peak→17.14ms/60,459B;8decodes. These are one local fixture comparison, not a hardware guarantee |
| 7. Changed embedding model synchronously reembedded the corpus | One background worker,32-row pages, no waiting refresh queue, generation fences and lexical fallback | Integration agent source/regressions; final measured/aggregate artifact pending |
| 8. Retry limits for different job types were mixed | Photo and background-AI recovery apply their own configured limit/type | Recovery regressions in owning lane; final aggregate evidence pending |

The integration agent reported an intermediate aggregate of2210Python tests/1skip,284frontend tests
and27native tests/3manual-default-ignored. Later updater/packaging/quality edits require a final rerun;
these numbers are deliberately not presented as the final release snapshot.

## Additional release-path gap closed in code

The audit also found that a stable release could pass with updater support disabled, and that
registering the plugin alone did not provide a user-facing update flow. The committed optional
`updater` Cargo feature now includes native check/install commands, local unconfigured status and
Settings controls. Native IPC accepts a checked version and explicit confirmation, never an update
URL/key/path. Downloads require HTTPS, reject downgrade/unsafe redirects, stop at512MiB and verify the upstream
signature plus signed app version before stopping Core. Installation is serialized with data moves/
model/key changes. Failure restores Core; success hands restart to Tauri/the Windows installer.

Stable preflight now requires the activated overlay/build feature, valid public-key format, secure
endpoint, signed-version enforcement, native runtime wiring, Tauri CLI2.12+ and signing-key presence.
Stable asset assembly rejects an empty or partial signed three-platform updater set. SemVer build
metadata containing a hyphen cannot bypass stable checks. CI compiles the feature for validation
builds and checks real codesign/notarization or Authenticode/timestamps after stable packaging.
The activation script only writes the public overlay, runs locked feature compilation and rolls back
on failure; it never generates a private key or patches source dependencies during activation.

Observed in this lane:32release/configurator/asset tests;3native updater tests with the optional
feature;2frontend updater tests; TypeScript/production build, Ruff, mypy and feature Clippy passed.
Native tests use a public upstream signature vector (payload `test`) and local interrupted,
oversized and downgrade-redirect HTTP fixtures. Tampered bytes, invalid signatures and signed-version
mismatch are rejected before install. No fixture package was installed and no production key was
used. A production-browser IPC fixture run passed9workspaces/shortcuts/responsive checks; it is
not signed-update runtime evidence. The updater confirmation remains open and busy until restart
or failure. The shared dialog now has a real fixed body portal overlay; real browser Tab/Escape/
backdrop/background-navigation checks keep focus and input protected, and a synthetic native
download failure closes the modal and exposes the error. Screenshots were inspected.

## Remaining production blockers and limits

- The integration agent observed an empty GitHub Actions secret-name list, no published releases and
  no existing long-lived updater key configuration. Only names/presence were checked; no secret
  value is included here. No replacement private key was generated.
- Apple Developer ID/notarization and Windows Authenticode credentials, durable updater-key backup/
  public trust-root activation and a matching signed stable tag remain required. Stable gates are
  expected to fail until those operator inputs exist.
- A physical Windows device was not available. Windows CI compilation/package smoke is useful
  evidence but does not close installed-device/OS-credential-store/update/recovery verification.
- Real signed no-update/update/bad-signature/interrupted-update checks on packaged Windows/macOS
  clients remain required. Synthetic signature/transport tests cannot replace them.
- Educational model quality is separate from structural acceptance. A real Gemma pilot still
  mistranslated “How are you?” as “잘 잤니”; the quality lane is revising its gates. Do not claim
  every activity kind/model is release-quality, or that a small synthetic sample proves usefulness.
- Representative minimum/recommended hardware and longitudinal household use remain sample-/device-
  specific. No actual household records, API keys or private certificates belong in this repository.

See [release operations](release.md), [operator handoff](operator-handoff.md),
[privacy boundaries](privacy-and-safety.md) and [material quality contract](material-quality-contract.md).
The final integration section will record exact source/build hashes, test totals, audit reports and
external CI links after the source snapshot is frozen.


## Packaging license follow-up

The existing table/link notice was insufficient as the only bundled attribution. The Core build now
creates a full-text license resource bundle from the installed58-entry Python runtime closure
(57third parties plus GrowWise), preserves wheel LICENSE/NOTICE/copyright bytes and includes Python/
bootloader support texts. Three wheels omit license files; four version/commit-pinned official files
are checked in with SHA-256 provenance rather than invented notices. Production Node and native
Cargo license collection is integrated and was exercised offline on this macOS host:57Python,
2bootloader-support,4Node and311Rust package rows. The pinned interpreter's native-component
notices form one additional row, including the distributor's8component texts and the exact
OpenSSL3.5.7 LICENSE/AUTHORS texts. Official commits and SHA-256 accompany those files; the
package workflow uses uv-managed Python3.12.13/build20260623 and rejects a different build until
its component notices are reviewed. This is technical preservation, not a complete legal opinion.
`licenses/` is a Tauri resource; hashes and Python graph parity
are CI checked. A shared environment containing development tools is rejected for sidecar builds.
Final clean-environment PyInstaller/packaged checks remain the integration agent's next evidence.
