import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";

describe("WorkspaceShell", () => {
  it("renders a labelled workspace region and a keyboard skip link without nesting main landmarks", () => {
    const html = renderToStaticMarkup(
      <WorkspaceShell initialView="materials" renderWorkspace={(view) => <section>{view} workspace</section>} />,
    );
    expect(html).toContain('data-active-workspace="materials"');
    expect(html).toContain('id="workspace-panel"');
    expect(html).toContain('role="region"');
    expect(html).toContain('aria-label="자료실 작업공간"');
    expect(html).toContain('href="#workspace-panel"');
    expect(html).toContain("작업공간 본문으로 바로가기");
    expect(html).toContain("materials workspace");
    expect((html.match(/<main/g) ?? []).length).toBe(1);
  });
});
