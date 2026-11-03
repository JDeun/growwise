# Observed follow-up of deep UI states

- Observed:2026-11-03; code revision:`e3c3b3b19d9fa23a42d976e39f7fee48af211d4b`.
- Extends [the top-level design check](design-validation-20261103.md); earlier artifacts and ledger rows remain unchanged.
- Impeccable4.8.0 pinned:`9fadc41729c38fd47d7ae622b501558653f9d2e9`, telemetry disabled.
- [Sanitized per-state measurements](design-validation-20261103-deep.json) preserve the failure and rescan separately.

The synthetic production-browser fixture visited20 states:profile3tabs, learning2tabs, materials4tabs,
and settings with all details open, at1440px and430px each. Every state had no horizontal document
overflow. The first scan found one distinct issue in both widths:the observation form followed the
page h1 with an h3. The section heading was corrected to h2, keeping its18px CSS role and geometry.

Only the affected observation state was rescanned at both widths after rebuilding. Each rescan
reported zero `quality` findings and no document overflow, loading `index-0ik4L8yG.js` and
`index-BzyA4bcz.css`. The18other states were already clear of quality-category findings in the
initial scan; they were not falsely reported as rerun. Existing nested-card style warnings remain.

The implementation agent directly inspected deep photo/profiledevelopment/discovery and430px
observation screenshots. This is render/reflow evidence with synthetic IPC data. Opening settings
details does not prove APIkey saving or OS credential-store mutation, and430px does not certify
browser zoom or assistive technology behavior. It does not replace the separately recorded
[actualCore14-step journey](live-core-browser-20261103-final.md), whose earlier exact asset names
remain accurate. No household records, credentials or device identifiers are included.
