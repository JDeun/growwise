import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceFrame } from "./WorkspaceFrame";

describe("WorkspaceFrame", () => {
  it("provides a labelled boundary for migrated content", () => {
    const html = renderToStaticMarkup(<WorkspaceFrame view="materials"><p>material content</p></WorkspaceFrame>);
    expect(html).toContain('aria-labelledby="workspace-materials-title"');
    expect(html).toContain("자료");
    expect(html).toContain("material content");
  });
});
