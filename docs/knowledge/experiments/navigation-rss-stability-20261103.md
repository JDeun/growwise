# Navigation RSS stability observation · 2026-11-03

The [original Linux CI failure](https://github.com/JDeun/growwise/actions/runs/41645495452) on
`974e512` measured Core RSS from 212,758,528 to 265,035,776 bytes: +52,277,248 bytes
(49.86 MiB). Most of that appeared in the first 30 seconds. Between 61 and 121 seconds RSS increased
only 12,288 bytes, with the final two samples equal. That is an observed plateau in this trace,
not proof of an allocator cause or absence of every leak. The original trace is preserved in the
[new JSON artifact](navigation-rss-stability-20261103.json), without changing its failed assertion.

The request-path review found transient 1000-record Pydantic lists and response serialization, closed
SQLite connection contexts, fixed-size path locks and bounded service caches. No accumulating fetched-record
cache or collection was found. Installed AnyIO releases its worker result/arguments explicitly.
Those observations motivate separating early high-water behavior from steady growth; they do not prove
which allocator or runtime mechanism caused this platform difference. No production memory code changed.

## Harness change

Three cycles are followed by a separate bounded warmup that must observe three RSS samples spanning
at least 30 seconds, spread no more than 512 KiB and no increase at every consecutive sample. It samples
every 15 seconds and refuses to start another cycle after 120 seconds without stability. Scheduling and one
in-flight bounded navigation cycle may extend the last sample slightly. Missing RSS or failure to reach
a plateau fails the run. Tests preserve the original cold-rise trace and reject sustained 4 KiB/15 second
growth, missing metrics, insufficient observation span and excessive oscillation.

The entire requested 120 second steady interval starts **after** this observation. Existing Core RSS
+32 MiB and post-GC browser heap +8 MiB limits remain unchanged. Artifacts retain the original baseline,
every warmup sample, absolute early growth and the separate steady samples. Linux additionally records
thread count and anonymous/file/shared RSS when available. Script, browser helper, metric-decision helper
and Core source fingerprints are pinned and checked at the end. This is not a threshold-only relaxation.

## Actual local result

Production UI plus authenticated actual Core passed 22 assertions with 1000 additional synthetic records.
Eight workspaces were exercised. AI features were disabled. The macOS arm64 run observed a plateau
at 106 seconds after 56 warmup cycles; early Core RSS increased
5,259,264bytes (5.02 MiB), and that increase remains visible in the artifact.
Then the full 120 second interval completed 64 cycles:

| Metric | Start | End | Change |
| --- | --- | --- | --- |
| Core RSS | 171,081,728bytes | 171,278,336bytes | +196,608bytes (0.188 MiB) |
| Post-GC browser heap | 5,932,424bytes | 6,115,264bytes | +182,840bytes (0.174 MiB) |
| Documents / listeners / nodes | 3 / 167 / 305 | 3 / 167 / 305 | unchanged |

Total observation after the initial three route cycles was 226 seconds. Two focused
Vitest files passed six tests, and the live script passed syntax validation. Exact helper/source hashes
and every metric sample are attached. This run did not independently re-audit screenshot design and is
not native-packaged execution; those remain separate validation lanes.

The next Linux CI result is intentionally not claimed here. Short synthetic RSS observation cannot rule
out small/noisy/late leaks, all data sizes or model-loaded operation. Actual household records stay private.

JSON SHA256: `254a1743f63e885353de35af21ecc314a76ce1b459d97486823c3ca92cf42e65`.
