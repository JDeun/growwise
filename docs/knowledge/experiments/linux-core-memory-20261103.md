# Linux Core memory lifecycle observation · 2026-11-03

[Actual Linux Live CI on afaa98c](https://github.com/JDeun/growwise/actions/runs/41654753604) passed
with the **unchanged** memory harness and limits. It observed a strict RSS plateau after 99 seconds,
then completed the entire requested interval: 121 seconds and 46 cycles across eight workspaces with
1000 additional synthetic records. Core RSS grew only 12,288 bytes during that interval; post-GC browser
heap grew 174,448 bytes. Threads remained 13, file RSS remained 28,909,568 bytes, and documents/listeners/
nodes remained 3/167/305. The large early rise remains in the artifact: 211,996,672→265,592,832 bytes
(+53,596,160 bytes), rather than disappearing behind a new baseline.

The [complete JSON evidence](linux-core-memory-20261103.json) preserves the exact successful report,
all earlier failed de3 warmup samples, three isolated Linux diagnostic runs and their exact probe source.
It extends the [local plateau observation](navigation-rss-stability-20261103.md) without rewriting it.

## Earlier failure remains visible

[de3cc07 Linux CI](https://github.com/JDeun/growwise/actions/runs/41650864448) failed because no strict
plateau was observed within the 120 second warmup. Its thread count stayed 13 and file RSS stayed
29,683,712 bytes, while anonymous RSS increased. Late samples at 64/81/96/112 seconds were
262,369,280 / 262,430,720 / 263,622,656 / 263,626,752 bytes: discrete late allocation steps prevented
that run from reaching the policy. It did not run or pass a steady interval. The later success does
not change the earlier failure into a pass or establish that every future environment will settle.

## Isolated actual-HTTP diagnosis

A new official `python:3.12.15-slim` container mounted the repository read-only and used disposable data.
Existing user containers were untouched. It ran the actual authenticated `secure_entry` Core with AI
and public enrichment disabled. This environment is Linux aarch64, CPython 3.12.15 and glibc 2.41;
GitHub CI is Linux x64. These are targeted API reproductions, not the same host or a full browser replay.
The diagnostic interpreter image is not the final packaged runtime recommendation.

Each run seeded 1000 records and made 153 cycles of seven real GET routes: learning records, resources,
photos, conversations, backups, growth map and Learning Wiki. Three cycles precede the baseline and
150 follow. Queries use six client workers; the server had 13 threads including the diagnostic monitor.
The first two runs use recent records. The paced run uses the UI soak's 365 day event-date distribution,
two-second minimum cycle cadence and 309.58 seconds total. Checkpoint GC and final `malloc_trim(0)`
are diagnostic-only wrapper operations; no product endpoint, periodic GC or allocator tuning was added.

| Run | Key observation |
| --- | --- |
| Tracemalloc 5 frames, 150 additional cycles | Post-GC retained Python growth 14,656 / 15,857 / 22,678 / 29,403 bytes at 25/50/100/150 cycles; no large retained-object growth observed |
| Same routes, tracing disabled | Post-GC object counts 153,219 / 153,228 / 153,220 / 153,221 / 153,220; final trim 162,914,304→132,636,672 bytes (released 30,277,632 bytes) |
| Paced five-minute run | Post-GC counts 153,220 / 153,221 / 153,221 / 153,221 / 153,221; trim 165,949,440→134,860,800 bytes (released 31,088,640 bytes) |

In the traced run, snapshot metadata itself heavily inflated RSS and object counts. Its absolute RSS is
not a production-memory measurement. Before/after GC and every retained-size comparison remain in the
artifact. In the untraced runs, GC did not itself reduce RSS, yet the final trim returned more pages than
the observed rise since baseline. That directly demonstrates allocator-held free pages in these cases,
while live Python objects remained nearly constant. It does not identify the cause of every CI increment
or exclude every possible native, slow, delayed or different-workload leak.

The unchanged strict helper, replayed on 15 second downsampled periodic paced-run metrics, first accepted
at 75 seconds: a 30 second span with 225,280 bytes spread and a flat intermediate sample. This is a helper
replay on diagnostic samples, not another UI assertion. Together with actual CI's 99 second result it
provides no observed reason to extend the 120 second deadline. It remains unchanged, as do the 512 KiB
warmup spread, sustained-growth rejection and Core +32 MiB / browser +8 MiB steady growth limits.

## Evidence boundary

This confirms one successful actual Linux UI/Core run and allocator-page release in isolated HTTP
reproductions. It is not proof of absence of all leaks, a memory capacity certificate, model-loaded
performance or household dogfooding. The synthetic source, response and metric paths contain no
household records, personal keys, host account paths or device identifiers. No signing/runtime release
approval is inferred. A later interpreter security migration or source change needs separate release CI.

JSON SHA256: `91f890c243c34edeac523b8f59ecc8bf56f3698b96086e5595b002320eb697dd`.
