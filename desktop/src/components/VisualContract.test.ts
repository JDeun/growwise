import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const accessibilityCss = readFileSync(
  fileURLToPath(new URL("../accessibility.css", import.meta.url)),
  "utf8",
);
const materialCss = readFileSync(
  fileURLToPath(new URL("./MaterialWorkspace.queue.css", import.meta.url)),
  "utf8",
);

describe("visual accessibility contracts", () => {
  it("keeps assistive-only labels visually hidden", () => {
    expect(accessibilityCss).toContain(".sr-only");
    expect(accessibilityCss).toContain("width: 1px");
    expect(accessibilityCss).toContain("overflow: hidden");
  });

  it("owns material option geometry instead of browser fieldset defaults", () => {
    expect(materialCss).toContain(".material-control-panel .material-kind-picker");
    expect(materialCss).toContain("border: 0");
    expect(materialCss).toContain(".material-control-panel .material-kind-option");
    expect(materialCss).toContain("grid-template-columns: 16px minmax(0, 1fr)");
    expect(materialCss).toContain("white-space: nowrap");
  });
});
