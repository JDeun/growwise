import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";

describe("WorkspaceShell", () => {
  it("renders an explicit workspace boundary while leaving the main landmark to the app", () => {
    const html = renderToStaticMarkup(
      <WorkspaceShell initialView="materials" renderWorkspace={(view) => <main>{view} workspace</main>} />,
    );
    expect(html).toContain('data-active-workspace="materials"');
    expect(html).toContain("materials workspace");
    expect((html.match(/<main/g) ?? []).length).toBe(1);
  });
});
