import { describe, expect, it } from "vitest";

import { DEFAULT_PRINT_LAYOUT, printPageRule, sanitizePrintLayout } from "./print-layout";

describe("print layout hardening", () => {
  it("falls back for non-object and invalid enum input", () => {
    expect(sanitizePrintLayout(null)).toEqual(DEFAULT_PRINT_LAYOUT);
    expect(sanitizePrintLayout({ paperSize: "<script>", orientation: "sideways", marginMm: "0" })).toEqual(DEFAULT_PRINT_LAYOUT);
  });

  it("clamps hostile or accidental margins", () => {
    expect(sanitizePrintLayout({ paperSize: "A4", orientation: "portrait", marginMm: -999 }).marginMm).toBe(5);
    expect(sanitizePrintLayout({ paperSize: "Letter", orientation: "landscape", marginMm: 999 }).marginMm).toBe(40);
    expect(sanitizePrintLayout({ paperSize: "A4", orientation: "portrait", marginMm: Number.NaN }).marginMm).toBe(18);
  });

  it("emits a constrained page rule", () => {
    expect(printPageRule({ paperSize: "Letter", orientation: "landscape", marginMm: 12 })).toBe(
      "@page { size: Letter landscape; margin: 12mm; }",
    );
  });
});
