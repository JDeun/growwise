# Explicit Python 3.12.16 local Core/UI validation · 2026-11-04

The coordinator's final local production UI and authenticated actual Core journey passed **22 assertions**
using an explicitly selected isolated Python 3.12.16 interpreter, rather than the shared development
virtual environment. The original report was written at 2026-11-04T00:00:01.688294+09:00 and remains unchanged.
The [public JSON](local-python31216-live-20261104.json) retains all report fields, including the
repeated final metric sample, with only its local output directory replaced by a placeholder.
Original report SHA256: `459fee6d42917478c598bc273a16142dd6f9b2448c2c6fb5bd53d6248a2c1658`.

## Runtime and invocation

The actual launch command set `GROWWISE_E2E_PYTHON` to the coordinator's private isolated interpreter.
The live harness uses that value for its Core subprocess. The exact command remains private; its hash
and a sanitized reproduction command are in the JSON. A separate direct `-I` stdlib probe against the
same interpreter after the journey independently returned:

| Component | Observed value |
| --- | --- |
| CPython | 3.12.16 |
| OpenSSL | OpenSSL 3.5.9 29 Sep 2026 |
| Expat | expat_2.9.0 |

No raw XML content, hostnames, user paths, credentials or interpreter search paths are published.
The journey report itself does not emit a Python-executable identity field: runtime attribution is
supported by the coordinator's explicit command, the harness's environment binding and the separate
version probe. It is not inferred from the default shared `.venv` interpreter.

```bash
# Replace placeholders with an isolated environment/artifact directory; run from desktop/.
GROWWISE_E2E_PYTHON=<isolated-python-3.12.16>/bin/python \
GROWWISE_E2E_ARTIFACTS=<isolated-artifacts> \
GROWWISE_E2E_SOAK_SECONDS=120 GROWWISE_E2E_SOAK_RECORDS=1000 npm run test:live
```

The frozen Core source fingerprint was independently recomputed at collection and matches the report.
Script/browser-helper/metric-helper fingerprints and exact production asset filenames are retained.
This source state matches the 09fc4f9 security-runtime change; no inference is made about later changes.

## Actual journey and memory interval

All 22 asserted steps passed, including parent review/use, material selection/print, independent records,
Learning Wiki and cited originals, conversation isolation/deletion, library mutation, real PNG originals
with bounded JPEG thumbnails, child switching, backup/restore, delayed-response isolation, selected
Markdown export and infant parent-guide print without learner worksheets. The shared print assertion
runs twice, so 22 is an assertion count rather than 22 independent features. AI features were disabled.

The existing RSS decision observed a plateau at 91 seconds after 48 warmup cycles. Its final 31 second
window spread 64 KiB and included a flat sample; the early RSS increase 6,307,840 bytes is preserved.
Only then did the full requested 120 second interval run: 64 cycles across eight workspaces with
1000 additional synthetic records.

| Metric | Steady start | Steady end | Change |
| --- | --- | --- | --- |
| Core RSS | 191,447,040 bytes | 186,613,760 bytes | -4,833,280 bytes |
| Post-GC browser heap | 5,891,024 bytes | 6,131,128 bytes | +240,104 bytes |
| Documents / listeners / nodes | 3 /167 /305 | 3 /167 /305 | unchanged |

Total observation after the initial preparation cycles was 211 seconds. The 120 second bounded warmup,
512 KiB stability window, monotonic-growth rejection and Core +32 MiB/browser +8 MiB steady budgets were
unchanged. A terminal RSS decrease is an observation, not a memory-improvement or no-leaks certificate.

## Scope and remaining evidence

This establishes actual local Core/browser behavior on the explicitly selected updated runtime. It
extends the [earlier local RSS evidence](navigation-rss-stability-20261103.md) without rewriting it,
and supplies new functional evidence after the [runtime security metadata correction](python-runtime-security-20261103.md).
It does not assert packaged-Tauri/WebView execution, Windows token-launch success, signed installer
release, malicious-input exploit validation, live provider/API-key behavior, new design inspection or
real household usefulness. Latest 09fc4f9 Linux Live CI is monitored separately and not marked passed
by this local result. Earlier model-quality and historical package artifacts retain their original scope.

JSON SHA256: `0fcc912183828746f7bb40efaf3a6388b21d41ada95d97e925c07e8b08c133db`.
