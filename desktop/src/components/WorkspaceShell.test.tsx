import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";

describe("WorkspaceShell", () => {
  it("renders an explicit workspace as the main region", () => {
    const html = renderToStaticMarkup(<WorkspaceShell initialView="materials" renderWorkspace={(view) => <p>{view} workspace</p>} />);
    expect(html).toContain('data-active-workspace="materials"');
    expect(html).toContain("materials workspace");
    expect(html).toContain("<main");
  });
});
