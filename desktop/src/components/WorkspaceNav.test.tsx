import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceNav } from "./WorkspaceNav";

const noop = () => undefined;

function countMatches(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

describe("WorkspaceNav accessibility", () => {
  it("labels the navigation landmark and its toolbar", () => {
    const html = renderToStaticMarkup(<WorkspaceNav active="home" onChange={noop} />);
    expect(html).toContain('aria-label="GrowWise 주요 메뉴"');
    expect(html).toContain('role="toolbar"');
    expect(html).toContain('aria-orientation="vertical"');
  });

  it("renders every menu item as a real button with an accessible label", () => {
    const html = renderToStaticMarkup(<WorkspaceNav active="home" onChange={noop} />);
    for (const label of ["홈", "기록", "성장", "활동", "학습자료", "자료실", "질문", "설정"]) {
      expect(html).toContain(`>${label}</span>`);
    }
    // Eight native buttons, so keyboard focus and Enter/Space activation are free.
    expect(countMatches(html, 'type="button"')).toBe(8);
    expect(html).not.toContain('role="button"');
  });

  it("marks the active view and keeps a single roving tab stop", () => {
    const html = renderToStaticMarkup(<WorkspaceNav active="materials" onChange={noop} />);
    // Exactly one item is in the tab order (roving tabindex).
    expect(countMatches(html, 'tabindex="0"')).toBe(1);
    expect(countMatches(html, 'tabindex="-1"')).toBe(7);
    expect(countMatches(html, 'aria-current="page"')).toBe(1);
    // The active item is the one that owns the tab stop and aria-current.
    const activeButton = html
      .split("<button")
      .find((chunk) => chunk.includes("학습자료"));
    expect(activeButton).toBeDefined();
    expect(activeButton).toContain('aria-current="page"');
    expect(activeButton).toContain('tabindex="0"');
  });
});
