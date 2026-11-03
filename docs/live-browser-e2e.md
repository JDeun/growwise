# Actual Core/browser validation

GrowWise's general-user desktop targets are Windows and macOS. The `Live Browser E2E` workflow therefore
runs independently on `windows-latest` and `macos-15-intel`, with separate `growwise-live-e2e-windows-latest`
and `growwise-live-e2e-macos-15-intel` artifacts. Failure of one does not cancel the other. Linux remains
useful for inexpensive Core/unit checks, but is not a public desktop release target.

The Intel macOS runner is a supported public target and avoids the observed long hosted ARM runner
queue. This browser matrix does not replace ARM package validation or the separately preserved actual
ARM Core/browser evidence; neither Mac architecture's result establishes the other's success.

Each job installs the reviewed pinned Python runtime, builds the production frontend and exercises the
authenticated actual Core with synthetic records. Only the native IPC transport is replaced by the
browser adapter; native Tauri/WebView startup and process-token checks still require the separate Native
Desktop E2E workflow. Neither browser job substitutes for a native packaged-app journey.

Both supported operating systems run the same eight-workspace soak with 1000 additional synthetic
records. Cold samples and absolute early growth remain in the artifact. Version 5 uses a fixed
representative warmup of at least 60 seconds **and** three complete eight-workspace cycles. The finite
setup deadline is 300 seconds; failure to complete the representative workload means failure. This
observational deadline is not an application startup SLA. The entire requested 120 second measurement
starts afterward. Every observed steady RSS sample must stay within +32 MiB of its starting baseline,
and every post-GC browser-heap sample within +8 MiB. Windows additionally requires positive private-byte
samples and at most +32 MiB private-byte growth independently of RSS. Missing measurements fail.

This replaces the earlier RSS-flatness release gate. Windows resident working sets can shrink, grow
and be paged independently of allocation retention; requiring a 512 KiB flat window was an unsupported
harness assumption. The actual Windows version-4 run declined from 129.8 MB to 112.1 MB while oscillating,
so its failed flatness criterion does not establish a memory leak. The old failure stays a failure;
the changed protocol requires new actual results. Neither the time limit nor growth budgets increase.

Windows reads the actual Core process's `Get-Process.WorkingSet64` and `PrivateMemorySize64` together;
macOS uses `ps` resident KiB
converted to bytes. The PID comes from Core's own isolated `.core.lock` owner metadata, written after it
acquires the data-directory lock. On Unix it must equal the spawned PID; on Windows a bounded
`Get-CimInstance` parent-chain check must reach the spawned process, allowing a Python venv redirecting
launcher without measuring that stub. Windows reads only metadata bytes after offset zero, preserving
the exclusive one-byte lock and avoiding a read of its protected region. See the upstream
[Windows byte-range lock semantics](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfile).
Only numeric PIDs are used; process command lines and environment
contents are not collected or published. The harness first verifies its own process can be measured,
then requires a positive valid
RSS value for every warmup and steady sample. Windows requires valid private bytes too. Missing data
fails rather than silently skipping the guard. Reports identify the operating system, methods, fixed
warmup policy, growth limits and assessment. The existing parent watchdog receives the Node host PID,
so a redirected Core also exits if its launcher or harness dies. Bounded observations do not establish the
absence of all slow/native leaks or household-scale performance.

Microsoft distinguishes [physical resident working-set pages](https://learn.microsoft.com/en-us/windows/win32/memory/working-set)
from [private-byte usage](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.privatememorysize64).
The latter supplies an additional Windows retention guard; RSS remains independently recorded and bounded.

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
