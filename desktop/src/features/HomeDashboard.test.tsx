import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ActiveChildProvider } from "../active-child-context";
import { HomeDashboard } from "./HomeDashboard";

function renderDashboard(active: boolean) {
  return renderToStaticMarkup(
    <ActiveChildProvider>
      <HomeDashboard active={active} onNavigate={vi.fn()} />
    </ActiveChildProvider>,
  );
}

describe("HomeDashboard", () => {
  it("stays out of non-home workspaces", () => {
    expect(renderDashboard(false)).toBe("");
  });

  it("announces the initial dashboard load politely", () => {
    const html = renderDashboard(true);
    expect(html).toContain("아이의 최근 기록을 정리하고 있습니다.");
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
  });
});
