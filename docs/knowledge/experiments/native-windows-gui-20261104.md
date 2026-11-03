# Actual Windows native GUI journey · 2026-11-04

The [actual Windows job](https://github.com/JDeun/growwise/actions/runs/41685029534/job/126088391773) completed the original WebView2 → Rust IPC →
authenticated managed Core journey. The workflow head is `f733bfc649859b2ee65d0f4b55f5ff791793df94`; the actual PR-merge checkout is `66ce275ce625cd45050efd8221e6955c94bd8d3d`.
This is a debug build of the production frontend and native handlers with the isolated
`io.github.jdeun.growwise.e2e` identifier. Business IPC and API responses were not replaced.

The [sanitized JSON](native-windows-gui-20261104.json) preserves the report, actual binary/script
hashes, driver provenance, filtered-token facts and screenshot hashes. It excludes raw logs,
environment contents, account SIDs and private host paths.

## Observed steps

1. actual WebView calls original Rust IPC; Desktop starts and authenticates a real AI-disabled Core in isolated E2E storage
2. UI first profile persists through real Rust -> Core IPC
3. UI generates a real template, explicitly approves it and saves an authoritative one-line learning result
4. real native file selection/upload/confirmation/thumbnail IPC succeeds; 2048x1536 PNG original remains byte-identical
5. UI child switching isolates real private search, materials, learning records and photo thumbnails
6. UI creates a real local backup; authoritative Markdown is durable on disk and no unhandled renderer errors occurred

The actual lock-owner PID was verified in the owned driver ancestry. Closing the driver/app
also stopped that exact Core process: `core_exited=true`. The report recorded no renderer errors.

## Windows execution boundary

The worker used a verified same-user Medium token with `TokenElevation=0` and Administrators
disabled, on `WinSta0\Default`. Its default ACL grants its own user access to future owned
objects so redirected pipes work after administrator filtering. Existing deny/allow ACEs remain;
machine policy and existing filesystem ACLs were not relaxed by that token fix.
The Microsoft driver download and matching runtime versions and its valid Authenticode state
are preserved in the JSON. This does not sign the GrowWise app.

## Scope and limits

All profiles, observations and the 2048×1536 PNG were synthetic. AI, vision, embeddings and
external enrichment were disabled. The test verifies manual/local record flows and the native
transport. It is not a physical Windows household trial, educational-effectiveness result,
model-quality test, paid remote API call or signed-installer certification. Packaged sidecar,
NSIS/DMG and attribution checks are recorded separately.

The earlier photo UI closed its disclosure after the first saved draft and hid confirmation.
The corrected UI keeps it open while a draft or pending job exists. A separate production
browser regression uses a physical CDP pointer to open a saved draft and requires visible
confirmation; this native journey uses original W3C clicks and rejects hidden/obstructed targets.

See [native reproduction instructions](../../native-e2e.md).

All five downloaded screenshots were visually inspected: empty home, persisted material result, committed photo thumbnail, private sibling search and completed backup. The material capture can still show save-busy styling after the backend observation has already persisted. This is not a full visual/accessibility audit.
