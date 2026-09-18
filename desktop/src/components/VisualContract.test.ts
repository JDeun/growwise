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

const mainSource = readFileSync(
  fileURLToPath(new URL("../main.tsx", import.meta.url)),
  "utf8",
);
const resourceCss = readFileSync(
  fileURLToPath(new URL("../features/ResourceLibrarySection.css", import.meta.url)),
  "utf8",
);
const discoveryCss = readFileSync(
  fileURLToPath(new URL("../features/DiscoveryWorkspace.css", import.meta.url)),
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

  it("keeps secondary material forms inside the GrowWise control language", () => {
    expect(resourceCss).toContain(".resource-filters input");
    expect(resourceCss).toContain("border-radius: 10px");
    expect(discoveryCss).toContain(".discovery-form input");
    expect(discoveryCss).toContain("box-shadow: 0 0 0 3px");
  });

  it("does not mount the redundant global approved-material print toolbar", () => {
    expect(mainSource).not.toContain("PrintApprovedMaterials");
  });
});
