import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const mainSource = readFileSync(
  fileURLToPath(new URL("../main.tsx", import.meta.url)),
  "utf8",
);
const shellCss = readFileSync(
  fileURLToPath(new URL("./WorkspaceShell.css", import.meta.url)),
  "utf8",
);

const PRODUCT_SURFACES = [
  ["home", "HomeDashboard"],
  ["profile", "ProfileWorkspaceHub"],
  ["learning", "LearningWorkspaceHub"],
  ["materials", "MaterialsWorkspaceHub"],
  ["photos", "PhotoActivityWorkspace"],
  ["help", "HelpWorkspace"],
] as const;

describe("product workspace composition contract", () => {
  it("wires each dedicated product workspace to a rendered surface", () => {
    for (const [workspace, component] of PRODUCT_SURFACES) {
      expect(mainSource, `${workspace} workspace must render ${component}`).toContain(component);
      expect(mainSource, `${workspace} workspace route is missing`).toContain(
        `activeView === "${workspace}"`,
      );
    }

    expect(mainSource).toContain("<App activeView={activeView} />");
  });

  it("keeps App-backed product surfaces projected without reviving removed sidebar tools", () => {
    for (const workspace of ["conversation", "backup", "settings"]) {
      expect(shellCss).toContain(`data-active-workspace="${workspace}"`);
    }

    expect(shellCss).toContain(".conversation-workspace-grid");
    expect(shellCss).toContain(".data-management-section");
    expect(shellCss).toContain("display: none");
    expect(mainSource).not.toContain('activeView === "observations"');
    expect(mainSource).not.toContain('activeView === "growth"');
    expect(mainSource).not.toContain('activeView === "activities"');
    expect(mainSource).not.toContain('activeView === "library"');
  });
});
