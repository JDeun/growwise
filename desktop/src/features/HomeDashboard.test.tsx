import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { HomeDashboard } from "./HomeDashboard";

describe("HomeDashboard", () => {
  it("stays out of non-home workspaces", () => {
    expect(renderToStaticMarkup(<HomeDashboard active={false} onNavigate={vi.fn()} />)).toBe("");
  });

  it("announces the initial home summary load politely", () => {
    const html = renderToStaticMarkup(<HomeDashboard active onNavigate={vi.fn()} />);
    expect(html).toContain("오늘의 GrowWise");
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
  });
});
