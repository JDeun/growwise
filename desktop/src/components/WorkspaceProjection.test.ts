import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const projectionCss = readFileSync(
  fileURLToPath(new URL("./WorkspaceShell.css", import.meta.url)),
  "utf8",
);
const sourceRoot = fileURLToPath(new URL("../", import.meta.url));

function collectTsxSource(directory: string): string {
  return readdirSync(directory, { withFileTypes: true })
    .filter((entry) => !entry.name.endsWith(".test.tsx"))
    .map((entry) => {
      const path = `${directory}/${entry.name}`;
      if (entry.isDirectory()) return collectTsxSource(path);
      return entry.name.endsWith(".tsx") ? readFileSync(path, "utf8") : "";
    })
    .join("\n");
}

const renderedSource = collectTsxSource(sourceRoot);

const projectedSurfaces = {
  profile: ["child-profile-section"],
  observations: ["observation-panel", "timeline-section"],
  growth: ["observation-panel"],
  activities: ["infant-guidance-section", "activity-section", "quest-section"],
  search: ["search-section", "conversation-section"],
  library: ["resource-section"],
  materials: ["material-workspace"],
  settings: ["status-grid", "data-management-section"],
} as const;

describe("legacy workspace projection contract", () => {
  it("keeps every projected workspace wired to a real rendered surface", () => {
    for (const [workspace, classes] of Object.entries(projectedSurfaces)) {
      expect(projectionCss, `${workspace} workspace selector is missing`).toContain(
        `data-active-workspace="${workspace}"`,
      );
      for (const className of classes) {
        expect(projectionCss, `${workspace} must project .${className}`).toContain(`.${className}`);
        expect(renderedSource, `render tree must still contain .${className}`).toContain(className);
      }
    }
  });

  it("keeps inactive legacy surfaces hidden before selectively projecting them", () => {
    for (const className of [
      "status-grid",
      "child-profile-section",
      "observation-panel",
      "search-section",
      "conversation-section",
      "resource-section",
      "material-workspace",
      "infant-guidance-section",
      "activity-section",
      "quest-section",
      "timeline-section",
      "data-management-section",
    ]) {
      expect(projectionCss).toContain(`.${className}`);
    }
    expect(projectionCss).toContain("display: none");
  });
});
