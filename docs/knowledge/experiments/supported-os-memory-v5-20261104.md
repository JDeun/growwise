# Windows and macOS actual Core/browser validation, version 5 · 2026-11-04

The [actual supported-OS CI](https://github.com/JDeun/growwise/actions/runs/41675184100) passed on both
Windows x64 and Intel macOS at revision `16a23fc33e81d715c28c77d819e3631dbb4b24ce`. A separate local
ARM macOS run passed with the same frozen Core and harness sources. Each run completed 22 assertions
against the authenticated actual Core, including restore, scoped records/conversations, original photos
and thumbnails, selected export, real PDF rendering and infant parent-guide printing. The repeated print
check counts twice; these are assertion counts, not 22 independent features per platform. AI was disabled.

The [full JSON](supported-os-memory-v5-20261104.json) preserves each original report, including all cold,
warmup and steady samples and emitted source/helper hashes. Only private artifact-directory paths are
replaced. Original report/log hashes and independent sample checks are included.

## Runtime and actual process identity

Both cloud environment-sync logs independently report `Using CPython 3.12.16`; cached setup-python
3.12.10 labels are not used as attribution. The local command explicitly selected an isolated 3.12.16
interpreter. A separate `-I` probe against that same local interpreter returned OpenSSL 3.5.9 and
Expat 2.9.0. Cloud SSL/Expat were not separately probed in this experiment.

Core writes its actual PID after acquiring the isolated data-directory lock. Unix checks that it equals
the spawned PID. Windows reads only metadata after the exclusively locked first byte, then verifies a
bounded CIM ancestry chain to the spawned process. The Windows result confirms an owned **descendant**,
so it measures the actual Python server rather than the roughly 4 MB venv redirecting launcher. Every
sample uses this verified server. No process command lines or environment contents are collected.
The existing parent watchdog receives the Node host PID in all three version-5 runs.

Each final emitted hash was independently checked against the pinned Git revision. Windows hashes
match exact LF→CRLF checkout bytes and Windows relative-path ordering; Unix hashes match Git LF bytes.
Different platform hashes therefore retain their actual meaning rather than being silently normalized.

## Fixed representative workload and measured growth

Version 5 first exercises all eight workspaces for **at least 60 seconds and three full cycles**, with
a 300 second setup bound. It then measures the **entire** requested 120 second interval with 1000 added
synthetic records distributed across a year. Cold samples and early absolute changes remain separate.

| Actual run | Warmup seconds / cycles | Measured seconds / cycles | Maximum Core RSS growth | Maximum private-byte growth | Maximum post-GC browser-heap growth |
| --- | --- | --- | --- | --- | --- |
| Windows x64 CI | 66 /25 | 122 /47 | 5,345,280 bytes | 6,447,104 bytes | 334,576 bytes |
| Intel macOS CI | 68 /9 | 121 /25 | 1,527,808 bytes | not measured | 323,212 bytes |
| ARM macOS local | 60 /32 | 122 /65 | 0 bytes | not measured | 483,188 bytes |

Every observed steady sample was positive, valid and within the unchanged **Core RSS +32 MiB / browser
heap +8 MiB** budgets. Windows additionally collected positive `PrivateMemorySize64` values alongside
`WorkingSet64` for the same verified server, and every private-byte sample remained within +32 MiB of
its steady baseline. The independent checks use the maximum across **all** observed samples, so a
transient sampled peak cannot be hidden by a later decrease. Documents/listeners/nodes remained
3 /167 /305 in all three runs.

Windows RSS ended 7,442,432 bytes below its steady start, while private bytes ended only 385,024 bytes
above it. This distinguishes resident-page movement from private-byte retention within this observed
interval. It does not establish the cause of every page movement or prove absence of slower/native leaks.

## Historical failures and scope

The [version-4 observations](supported-os-live-20261104.md) preserve the earlier Windows actual-server
RSS-flatness failure, the invalid launcher-only memory measurement and corrected restore/print harness
races. Version 5 changes the unsupported physical-flatness assumption to a fixed representative workload;
it does not relabel old failures or increase memory-growth limits. Windows private bytes add a separate
retention guard. This document records **new measured passes** under that explicit protocol.

These runs use the production frontend and actual authenticated Core with a browser IPC adapter. They
do not replace native Tauri/WebView GUI or packaged-installer verification. Hosted CI and concurrent
local validation are not idle-hardware benchmarks. AI, embedding, vision and public-enrichment features
were disabled, so no model-memory, provider, personal API-key or educational-quality claim follows.
The synthetic interval is not household dogfooding, malicious-input exploit validation, every-leak
absence, toy certification or measured learning effectiveness. No private household records, keys,
hostnames, raw XML, logs or private paths are published.

JSON SHA256: `d9c338d4304920638a0d65576d44e2884f49b82a629158015c76db03076ab7d6`.
