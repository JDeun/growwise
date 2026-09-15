import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceNav } from "./WorkspaceNav";

describe("WorkspaceNav", () => {
  it("marks the active workspace and renders all registered destinations", () => {
    const html = renderToStaticMarkup(<WorkspaceNav activeView="home" onChange={vi.fn()} />);
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("홈");
    expect(html).toContain("자료");
    expect(html).toContain("설정");
  });
});
