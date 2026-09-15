import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceNav } from "./WorkspaceNav";

describe("WorkspaceNav", () => {
  it("exposes the workspace switcher as a tablist with one selected tab", () => {
    const html = renderToStaticMarkup(<WorkspaceNav activeView="home" onChange={vi.fn()} />);
    expect(html).toContain('role="tablist"');
    expect(html).toContain('role="tab"');
    expect(html).toContain('aria-selected="true"');
    expect(html).toContain('aria-controls="workspace-panel"');
    expect(html).toContain('id="workspace-tab-home"');
    expect(html).toContain("홈");
    expect(html).toContain("자료");
    expect(html).toContain("설정");
  });
});
