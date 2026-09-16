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

  it("announces the initial home summary load politely", () => {
    const html = renderDashboard(true);
    expect(html).toContain("오늘의 GrowWise");
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
  });
});
