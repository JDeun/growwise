# Supported-OS browser/Core observations · 2026-11-04

The [actual version-4 run](https://github.com/JDeun/growwise/actions/runs/41671460632), revision
`48ba79b9776a63433cc9ff4183d635df78908f56`, passed on Intel macOS and failed its RSS-flatness setup
criterion on Windows. Both actual environment-sync logs selected **CPython 3.12.16**; the cached
setup-python 3.12.10 label is not used as runtime attribution. The [JSON](supported-os-live-20261104.json)
preserves the full sanitized reports, cold traces, source identities and original artifact/log hashes.

## Intel macOS: actual pass

All 22 assertions passed, including actual backup/restore, scoped conversation and learning records,
PNG/thumbnail handling, selected-record export, infant guide print and real rendered PDFs. The print
assertion runs twice, so this is an assertion count rather than 22 independent features. AI was disabled.
The existing data-directory lock metadata identified the measured Core as the spawned process.

With 1000 additional synthetic records, version 4 observed its required plateau after 163 seconds. The
entire subsequent 122 second measurement completed 26 cycles across eight workspaces:

| Metric | Observed value |
| --- | --- |
| Core RSS start → end | 152,834,048 →153,284,608 bytes |
| Core RSS change | +450,560 bytes |
| Maximum observed steady RSS growth | +466,944 bytes |
| Post-GC browser-heap change / maximum growth | +233,428 bytes |
| Documents / listeners / nodes | 3 /167 /305 throughout |

Every RSS sample was positive and valid; every observed steady RSS/heap sample remained within the
existing +32 MiB/+8 MiB allowances. Early RSS growth +5,201,920 bytes is retained separately. This is
Intel-hosted browser-to-Core evidence, not native WebView, ARM equivalence or all-leaks certification.

## Windows: actual server identified, old flatness criterion failed

The Windows Python venv executable was a redirecting launcher. The harness read the actual Core's
own `.core.lock` PID metadata, avoiding its exclusively locked first byte, and verified that its
bounded CIM parent chain reached the process it spawned. The reported identity is therefore a verified
owned descendant, not the launcher. No process command lines or environments were collected.

The measured Core started at 129,810,432 bytes RSS, oscillated between roughly 105 and 130 MB, and
ended at 112,148,480 bytes: **−17,661,952 bytes**. It completed 126 warmup cycles; the last sample was at
296 seconds. The last 33 second window spread 2,035,712 bytes, exceeding the old 512 KiB flatness rule,
so the 300 second setup failed and **no 120 second measurement interval began**. This remains a failed
version-4 run. Falling/oscillating RSS neither proves a retained-object leak nor proves private
allocation stability, since this run did not collect private bytes.

Microsoft defines the [working set as physical resident pages](https://learn.microsoft.com/en-us/windows/win32/memory/working-set)
and separately documents [private-byte usage](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.privatememorysize64).
The unsupported requirement for physically flat RSS was a harness assumption, not a product requirement.
Version 5 corrects the protocol to a fixed representative warmup of at least 60 seconds and three full
workspace cycles, still bounded by 300 seconds, followed by the entire requested 120 second interval.
It retains the +32 MiB RSS/+8 MiB browser budgets and checks **every** observed steady sample; Windows
also requires positive private-byte samples and an independent +32 MiB private-byte growth budget.
This changes the measurement protocol, not its memory-growth allowances or the historical result.
New version-5 OS results are required and are not asserted by this artifact.

## Earlier harness failures remain preserved

- [792c Windows](https://github.com/JDeun/growwise/actions/runs/41666654909): the old test treated a restored
  child count as completion while restore was still rebuilding projections. A pre-completion conversation
  request correctly failed its generation fence. An isolated actual HTTP reproduction established that
  this returns 503, while a fresh request after the completed restore response returns 200. The harness
  now waits for the awaited UI restore-success response; it does not retry around or relax the fence.
- [8ee Windows](https://github.com/JDeun/growwise/actions/runs/41669736206): 22 functional assertions passed,
  but its roughly 4 MB RSS measurement belonged to the venv launcher. The original sanitized report
  remains in the JSON with an explicit invalid-Core-memory interpretation. It is functional evidence
  only, not a Core-memory pass.
- The same 8ee Intel run inspected print details before the newly approved card finished rendering.
  Waiting for the actual approved card and details resolved that harness race; the 48ba Intel run
  passed both real PDF assertions.

Windows checkout CRLF explains its differing actual source-byte hashes. The earlier 8ee Core and all
three helper hashes were independently matched exactly to the pinned Git sources with LF→CRLF conversion;
they are not silently replaced by Unix hashes. Failed Windows 48ba did not reach final report/source
equality assertions, so its expected CRLF hashes are labeled revision-derived rather than emitted.

The subsequent harness configuration also enables the already implemented parent watchdog with the
Node host PID, so redirected children exit when their launcher or harness dies; 12 existing watchdog
tests passed. This one-line setting was not present in the 48ba run and is not claimed as new OS proof.
No production source, model, household data or release installer changed in this experiment.

The [Linux diagnosis](linux-core-memory-20261103.md) and [Linux 3.12.16 failed setup](linux-python31216-boundary-20261104.md)
remain separate historical diagnostics. Windows and macOS are the public desktop targets. Browser
adapter evidence does not replace the separate native GUI and packaged-runtime validations.
