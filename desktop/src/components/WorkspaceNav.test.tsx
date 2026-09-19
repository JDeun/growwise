import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceNav } from "./WorkspaceNav";

describe("WorkspaceNav", () => {
  it("exposes only the product navigation and utility items", () => {
    const html = renderToStaticMarkup(<WorkspaceNav activeView="home" onChange={vi.fn()} />);
    expect(html).toContain('<nav class="workspace-nav" aria-label="GrowWise 주요 메뉴">');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain('aria-controls="workspace-panel"');
    expect(html).toContain('id="workspace-nav-home"');
    expect(html).toContain("GrowWise");
    expect(html).toContain("대시보드");
    expect(html).toContain("아이 프로필");
    expect(html).toContain("학습 기록");
    expect(html).toContain("자료실");
    expect(html).toContain("사진첩");
    expect(html).toContain("대화하기");
    expect(html).toContain("백업 및 복원");
    expect(html).toContain("설정");
    expect(html).toContain("도움말");

    expect(html).not.toContain("추가 도구");
    expect(html).not.toContain("관찰 기록");
    expect(html).not.toContain("성장 보기");
    expect(html).not.toContain("자료 찾기");
    expect(html).not.toContain("참고 자료");
    expect(html).not.toContain("Local-first");
  });
});
