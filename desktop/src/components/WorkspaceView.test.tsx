import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceView } from "./WorkspaceView";

describe("WorkspaceView", () => {
  it("renders only the active slot", () => {
    const slots = { home: <p>home slot</p>, materials: <p>materials slot</p> };
    expect(renderToStaticMarkup(<WorkspaceView activeView="home" slots={slots} />)).toContain("home slot");
    expect(renderToStaticMarkup(<WorkspaceView activeView="materials" slots={slots} />)).toContain("materials slot");
  });
});
