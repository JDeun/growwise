import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const accessibilityCss = readFileSync(
  fileURLToPath(new URL("../accessibility.css", import.meta.url)),
  "utf8",
);
const tokensCss = readFileSync(
  fileURLToPath(new URL("../tokens.css", import.meta.url)),
  "utf8",
);
const shellCss = readFileSync(
  fileURLToPath(new URL("./WorkspaceShell.css", import.meta.url)),
  "utf8",
);
const dashboardCss = readFileSync(
  fileURLToPath(new URL("../features/HomeDashboard.css", import.meta.url)),
  "utf8",
);
const profileCss = readFileSync(
  fileURLToPath(new URL("../features/ProfileWorkspaceHub.css", import.meta.url)),
  "utf8",
);
const learningCss = readFileSync(
  fileURLToPath(new URL("../features/LearningRecordWorkspace.css", import.meta.url)),
  "utf8",
);
const conversationCss = readFileSync(
  fileURLToPath(new URL("../features/SearchConversationSection.css", import.meta.url)),
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

  it("locks the approved GrowWise shell and brand geometry", () => {
    expect(tokensCss).toContain("--bg: #fbf9f6");
    expect(tokensCss).toContain("--ink: #2b2a28");
    expect(tokensCss).toContain("--primary: #2f8f6b");
    expect(tokensCss).toContain("--leaf: #a7d7a0");
    expect(tokensCss).toContain("--stone: #9ca3af");
    expect(tokensCss).toContain("--product-shell-max: 1540px");
    expect(tokensCss).toContain("--product-sidebar-width: 232px");
    expect(tokensCss).toContain("--product-topbar-height: 62px");
    expect(tokensCss).toContain("--product-panel-radius: 17px");
    expect(shellCss).toContain(
      "grid-template-columns: var(--product-sidebar-width) minmax(0, 1fr)",
    );
    expect(shellCss).toContain("min-height: var(--product-topbar-height)");
    expect(shellCss).toContain("width: min(420px, 42vw)");
    expect(shellCss).toContain("border-radius: 999px");
    expect(shellCss).toContain("width: 42px");
  });

  it("locks concept-derived desktop workspace proportions", () => {
    expect(dashboardCss).toContain(
      "grid-template-columns: minmax(300px, 0.84fr) minmax(0, 1.16fr)",
    );
    expect(profileCss).toContain(
      "grid-template-columns: minmax(250px, .80fr) minmax(0, 2.20fr)",
    );
    expect(profileCss).toContain("width: 112px");
    expect(profileCss).toContain("height: 112px");
    expect(learningCss).toContain(
      "grid-template-columns: minmax(210px, 0.72fr) minmax(260px, 0.92fr) minmax(360px, 1.36fr)",
    );
    expect(materialCss).toContain(
      "grid-template-columns: minmax(0, 2.04fr) minmax(300px, .96fr)",
    );
    expect(conversationCss).toContain(
      "grid-template-columns: minmax(190px, .67fr) minmax(420px, 1.22fr) minmax(320px, 1.11fr)",
    );
  });
});
