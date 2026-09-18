import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceNav } from "./WorkspaceNav";

describe("WorkspaceNav", () => {
  it("exposes a grouped sidebar navigation with one current workspace", () => {
    const html = renderToStaticMarkup(<WorkspaceNav activeView="home" onChange={vi.fn()} />);
    expect(html).toContain('<nav class="workspace-nav" aria-label="GrowWise 주요 메뉴">');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain('aria-controls="workspace-panel"');
    expect(html).toContain('id="workspace-nav-home"');
    expect(html).not.toContain('role="tablist"');
    expect(html).not.toContain('role="tab"');
    expect(html).toContain("Workspace");
    expect(html).toContain("More");
    expect(html).toContain("아이 프로필");
    expect(html).toContain("AI 학습자료");
    expect(html).toContain("백업 및 설정");
  });
});
