import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const mainSource = readFileSync(
  fileURLToPath(new URL("../main.tsx", import.meta.url)),
  "utf8",
);
const appSource = readFileSync(
  fileURLToPath(new URL("../App.tsx", import.meta.url)),
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
    expect(mainSource).toContain("<App activeView={activeView} onNavigate={navigate} />");
  });

  it("mounts feature surfaces from App instead of reviving them through shell CSS", () => {
    expect(appSource).toContain('activeView === "conversation"');
    expect(appSource).toContain('activeView === "backup"');
    expect(appSource).toContain('activeView === "settings"');
    expect(appSource).toContain("showProfile");
    expect(appSource).toContain("showMaterials");
    expect(appSource).toContain("showTimeline");

    expect(shellCss).not.toContain('data-active-workspace="profile"] .app-shell');
    expect(shellCss).not.toContain('data-active-workspace="materials"] .app-shell');
    expect(shellCss).toContain('data-active-workspace="growth"');
  });

  it("does not expose removed legacy routes in the product composition", () => {
    expect(mainSource).not.toContain('activeView === "observations"');
    expect(mainSource).not.toContain('activeView === "growth"');
    expect(mainSource).not.toContain('activeView === "activities"');
    expect(mainSource).not.toContain('activeView === "library"');
  });
});
