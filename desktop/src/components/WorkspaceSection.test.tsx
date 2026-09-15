import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspaceSection } from "./WorkspaceSection";

describe("WorkspaceSection", () => {
  it("renders only the selected workspace", () => {
    expect(renderToStaticMarkup(<WorkspaceSection activeView="home" view="home"><p>home content</p></WorkspaceSection>)).toContain("home content");
    expect(renderToStaticMarkup(<WorkspaceSection activeView="materials" view="home"><p>home content</p></WorkspaceSection>)).toBe("");
  });
});
