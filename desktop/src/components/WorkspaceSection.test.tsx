import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceSection } from "./WorkspaceSection";

describe("WorkspaceSection", () => {
  it("renders only the selected workspace", () => {
    const { rerender } = render(
      <WorkspaceSection activeView="home" view="home">
        <p>home content</p>
      </WorkspaceSection>,
    );

    expect(screen.getByText("home content")).toBeTruthy();

    rerender(
      <WorkspaceSection activeView="materials" view="home">
        <p>home content</p>
      </WorkspaceSection>,
    );

    expect(screen.queryByText("home content")).toBeNull();
  });
});
