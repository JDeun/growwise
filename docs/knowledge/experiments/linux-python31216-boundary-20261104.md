# Linux Python 3.12.16 observation boundary · 2026-11-04

The actual [b074175 Linux Live run](https://github.com/JDeun/growwise/actions/runs/41662105470)
**failed** its bounded RSS warmup. The install log selected reviewed CPython 3.12.16 and the environment
sync independently logged `Using CPython 3.12.16`. The harness then launches that repository environment's
interpreter. This runtime attribution comes from the actual job, rather than its cached setup-python label.
The [JSON](linux-python31216-boundary-20261104.json) preserves the complete original metric artifact,
original artifact/log hashes and revision-derived Core/helper identities. A failed journey does not reach
the final report/source-equality assertions, so those identities are explicitly labeled revision-derived.

## Failed observation and bounded follow-up

After 1000 added synthetic records, 43 warmup cycles across eight workspaces produced these late samples:

| Elapsed | Core RSS |
| --- | --- |
| 78 seconds | 263,110,656 bytes |
| 96 seconds | 264,290,304 bytes |
| 111 seconds | 264,290,304 bytes |

The last three samples spanned 33 seconds but spread 1,179,648 bytes, above the unchanged 512 KiB
stability limit. Threads remained 13 and file-backed RSS remained 29,331,456 bytes. Total early RSS growth
was 44,244,992 bytes. The full requested 120 second steady interval **did not start**. Two equal samples
15 seconds apart are insufficient to claim the required 30 second observed plateau. No later sample is
invented, and this run is not marked passed by earlier local or differently versioned Linux evidence.

The next harness revision changes only the finite observation setup deadline from 120 to 300 seconds.
The 120 second value was an observational setup bound, not an application startup SLA. The late 1.18 MiB
step and subsequent flat sample justify measuring whether an actual later plateau occurs. The earlier
[isolated Linux probes](linux-core-memory-20261103.md) found roughly 29 KiB retained Python growth after
153 cycles and directly returned roughly 30 MiB of native pages with diagnostic-only allocator trimming.
Those observations support distinguishing a setup timeout from a confirmed retained-object leak; they do
not prove the cause of every CI RSS increase or establish absence of all leaks.

All acceptance conditions remain: three samples spanning at least 30 seconds, spread at most 512 KiB,
rejection when every consecutive sample increases, followed by the **entire** requested 120 second steady
interval with Core +32 MiB and post-GC browser +8 MiB budgets. Cold samples and absolute early growth remain
published. There are no production GC/allocator-trim calls, hidden retries or production memory changes.
If stability is not observed within 300 seconds, the next run fails; another failure requires diagnosis,
not another deadline increase. The seven focused decision/protocol regressions passed, including sustained
4 KiB growth every 15 seconds through 300 seconds. The next actual CI result remains pending here.

## Earlier runtime drift remains separate

The [09fc4f9 Linux run](https://github.com/JDeun/growwise/actions/runs/41659702439) passed, with a plateau at
96 seconds followed by 122 seconds/49 cycles: Core RSS +49,152 bytes and browser heap +290,032 bytes.
However, its actual sync selected **CPython 3.14.4** because the cached 3.12.15 did not satisfy the new source
floor. Its full sanitized report is retained as historical compatibility evidence, **not Python 3.12.16
proof**. The new central runtime installation and project-version pin prevent that selection drift.
The [separate local explicit 3.12.16 result](local-python31216-live-20261104.md) remains valid within its
own macOS scope and does not substitute for the failed Linux run.

## Typing-only model source extension

The revision also replaces an inferred provider return type with a `typing.cast` union around the same
runtime value. Prompts, schemas, gates and publication behavior are unchanged. All 51 stored actual
candidates from the [immutable repeated-quality experiment](model-repeat-quality-20261103.md) were replayed
through the updated production service without new inference. Every classification and full final
material/parent-guide hash matched: 45 accepted AI drafts, five quality fallbacks and one safety fallback.
The JSON records every comparison and both material-source hashes. The three focused material test files
passed 85 tests. This extends the exact stored-output evidence to a typing-only revision; it does not
claim new model performance, universal educational quality or measured learning effectiveness.

Only synthetic aggregate metrics, source identities and content hashes are published. No raw logs,
hostnames, private filesystem paths, XML, credentials or household records are included. No new screenshot
design review, native Windows launch, packaged-runtime success or external API-key test is asserted.
