import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";

describe("WorkspaceShell", () => {
  it("renders a labelled workspace region and the shared product topbar", () => {
    const html = renderToStaticMarkup(
      <WorkspaceShell initialView="materials" renderWorkspace={(view) => <section>{view} workspace</section>} />,
    );
    expect(html).toContain('data-active-workspace="materials"');
    expect(html).toContain('id="workspace-panel"');
    expect(html).toContain('role="region"');
    expect(html).toContain('aria-label="자료실 작업공간"');
    expect(html).toContain('href="#workspace-panel"');
    expect(html).toContain("작업공간 본문으로 바로가기");
    expect(html).toContain('aria-label="대화와 기록 검색으로 이동"');
    expect(html).toContain('aria-label="알림"');
    expect(html).toContain('aria-label="아이 프로필로 이동"');
    expect(html).not.toContain("새 기록");
    expect(html).toContain("materials workspace");
    expect((html.match(/<main/g) ?? []).length).toBe(1);
  });
});
