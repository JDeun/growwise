export const PAPER_SIZES = ["A4", "Letter"] as const;
export type PaperSize = (typeof PAPER_SIZES)[number];
export const PRINT_ORIENTATIONS = ["portrait", "landscape"] as const;
export type PrintOrientation = (typeof PRINT_ORIENTATIONS)[number];

export type PrintLayout = {
  paperSize: PaperSize;
  orientation: PrintOrientation;
  marginMm: number;
};

export const DEFAULT_PRINT_LAYOUT: PrintLayout = {
  paperSize: "A4",
  orientation: "portrait",
  marginMm: 18,
};

const MIN_MARGIN_MM = 5;
const MAX_MARGIN_MM = 40;

export function sanitizePrintLayout(value: unknown): PrintLayout {
  if (!value || typeof value !== "object") return DEFAULT_PRINT_LAYOUT;
  const candidate = value as Partial<PrintLayout>;
  const paperSize = PAPER_SIZES.includes(candidate.paperSize as PaperSize)
    ? (candidate.paperSize as PaperSize)
    : DEFAULT_PRINT_LAYOUT.paperSize;
  const orientation = PRINT_ORIENTATIONS.includes(candidate.orientation as PrintOrientation)
    ? (candidate.orientation as PrintOrientation)
    : DEFAULT_PRINT_LAYOUT.orientation;
  const margin = typeof candidate.marginMm === "number" && Number.isFinite(candidate.marginMm)
    ? Math.min(MAX_MARGIN_MM, Math.max(MIN_MARGIN_MM, candidate.marginMm))
    : DEFAULT_PRINT_LAYOUT.marginMm;
  return { paperSize, orientation, marginMm: margin };
}

export function printPageRule(layout: PrintLayout): string {
  const safe = sanitizePrintLayout(layout);
  return `@page { size: ${safe.paperSize} ${safe.orientation}; margin: ${safe.marginMm}mm; }`;
}
