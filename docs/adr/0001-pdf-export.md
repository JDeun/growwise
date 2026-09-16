# ADR 0001 — PDF export uses the OS-native print pipeline

- Status: Accepted
- Date: 2026-09-16

## Context

GrowWise needs printable and PDF-saveable parent-approved learning materials on both Windows and macOS.
The Desktop already renders material content in the WebView, gates use/export to approved material, and
supports A4/Letter, portrait/landscape, and bounded print margins through `desktop/src/print-layout.ts`.

A separate PDF renderer would create a second rendering stack. For Korean and mixed-language material it
would also require an explicit font discovery/bundling policy, additional binary/runtime dependencies, and
new parity tests to keep WebView preview output aligned with PDF output.

## Decision

GrowWise uses the **OS-native print pipeline as its PDF renderer and packaging strategy** for the desktop
product.

- The WebView HTML/CSS representation remains the canonical printable representation.
- `desktop/src/print-layout.ts` owns safe page-size, orientation, and margin inputs.
- Only parent-approved material is eligible for print/PDF output.
- The operating-system print dialog owns printer selection and PDF destination selection.
- GrowWise does not write arbitrary PDF paths directly from WebView content.
- Desktop packages do not add a separate headless browser, PDF engine, or bundled CJK font solely for PDF
  export.

This keeps print and PDF output on the same rendering path users review before export and preserves the
current offline-first desktop boundary.

## Consequences

### Positive

- No second Markdown/HTML-to-PDF renderer can drift from the reviewed Desktop rendering.
- No additional PDF-runtime dependency or font redistribution surface is added.
- Existing Windows and macOS package validation exercises the same application that opens the print flow.
- Page settings stay constrained by the existing sanitizer rather than accepting arbitrary CSS from user
  input.

### Trade-offs

- PDF bytes are not guaranteed to be deterministic across operating systems or OS versions.
- Background/headless batch PDF generation is intentionally out of scope.
- Printer-specific headers, scaling, and destination controls remain OS concerns.

## Revisit when

Adopt a dedicated PDF engine only if GrowWise later requires unattended batch export, byte-stable archival
PDFs, or output that must be identical across Windows and macOS. That change must include a licensed CJK
font strategy, cross-platform rendering parity tests, and installer-size/dependency review.
