import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";

describe("WorkspaceShell", () => {
  it("renders a labelled workspace panel and a keyboard skip link without nesting main landmarks", () => {
    const html = renderToStaticMarkup(
      <WorkspaceShell initialView="materials" renderWorkspace={(view) => <main>{view} workspace</main>} />,
    );
    expect(html).toContain('data-active-workspace="materials"');
    expect(html).toContain('id="workspace-panel"');
    expect(html).toContain('role="tabpanel"');
    expect(html).toContain('aria-labelledby="workspace-tab-materials"');
    expect(html).toContain('href="#workspace-panel"');
    expect(html).toContain("작업공간 본문으로 바로가기");
    expect(html).toContain("materials workspace");
    expect((html.match(/<main/g) ?? []).length).toBe(1);
  });
});
