import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceView } from "./WorkspaceView";

describe("WorkspaceView", () => {
  it("renders only the active slot", () => {
    const slots = {
      home: <p>home slot</p>,
      materials: <p>materials slot</p>,
    };
    const { rerender } = render(<WorkspaceView activeView="home" slots={slots} />);

    expect(screen.getByText("home slot")).toBeTruthy();
    expect(screen.queryByText("materials slot")).toBeNull();

    rerender(<WorkspaceView activeView="materials" slots={slots} />);
    expect(screen.getByText("materials slot")).toBeTruthy();
    expect(screen.queryByText("home slot")).toBeNull();
  });
});
