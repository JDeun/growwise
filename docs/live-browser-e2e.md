# Actual Core/browser validation

GrowWise's general-user desktop targets are Windows and macOS. The `Live Browser E2E` workflow therefore
runs independently on `windows-latest` and `macos-latest`, with separate `growwise-live-e2e-windows-latest`
and `growwise-live-e2e-macos-latest` artifacts. Failure of one does not cancel the other. Linux remains
useful for inexpensive Core/unit checks, but is not a public desktop release target.

Each job installs the reviewed pinned Python runtime, builds the production frontend and exercises the
authenticated actual Core with synthetic records. Only the native IPC transport is replaced by the
browser adapter; native Tauri/WebView startup and process-token checks still require the separate Native
Desktop E2E workflow. Neither browser job substitutes for a native packaged-app journey.

Both supported operating systems run the same eight-workspace soak with 1000 additional synthetic
records. Cold RSS samples and absolute early growth remain in the artifact. Before the full 120 second
steady interval, the harness must observe three samples spanning at least 30 seconds, with no more than
512 KiB spread and without every consecutive sample increasing. The finite setup deadline is 300 seconds;
no observed stability means failure. This observational deadline is not an application startup SLA.
The subsequent full steady interval retains the Core +32 MiB and post-GC browser +8 MiB growth limits.

Windows reads the measured Core process's `Get-Process.WorkingSet64`; macOS uses `ps` resident KiB
converted to bytes. The PID comes from the spawned child and must be a positive integer before command
construction. The harness first verifies its own process can be measured, then requires a positive valid
RSS value for every warmup and steady sample. Missing RSS fails rather than silently skipping the guard.
Reports identify the operating system and RSS method; working-set observations do not establish the
absence of all slow/native leaks or household-scale performance.

The platform alignment follows the supported product targets. It does not turn the historical
[Python 3.12.16 Linux failure](knowledge/experiments/linux-python31216-boundary-20261104.md) into a pass,
or invalidate the scope of the [Linux allocator investigation](knowledge/experiments/linux-core-memory-20261103.md).
Those artifacts remain immutable historical evidence. Configuring this matrix alone does not establish
new macOS/Windows success; each platform's actual workflow result and runtime identity must be checked.

For an equivalent local run after installing the locked dependencies and building `desktop/`:

```bash
GROWWISE_E2E_SOAK_SECONDS=120 GROWWISE_E2E_SOAK_RECORDS=1000 npm run test:live
```

```powershell
$env:GROWWISE_E2E_SOAK_SECONDS = '120'
$env:GROWWISE_E2E_SOAK_RECORDS = '1000'
npm run test:live
```

An explicitly selected isolated Core interpreter can be supplied with `GROWWISE_E2E_PYTHON`.
Keep real household records and private paths out of public validation artifacts.
