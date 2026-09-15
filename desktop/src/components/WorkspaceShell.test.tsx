import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";
import { LAST_WORKSPACE_KEY } from "./workspaceStorage";

describe("WorkspaceShell", () => {
  beforeEach(() => window.localStorage.clear());

  it("owns navigation state and persists the selected workspace", () => {
    render(<WorkspaceShell renderWorkspace={(view) => <p>{view} workspace</p>} />);

    expect(screen.getByText("home workspace")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /자료/ }));
    expect(screen.getByText("materials workspace")).toBeTruthy();
    expect(window.localStorage.getItem(LAST_WORKSPACE_KEY)).toBe("materials");
  });

  it("restores the last valid workspace", () => {
    window.localStorage.setItem(LAST_WORKSPACE_KEY, "growth");
    render(<WorkspaceShell renderWorkspace={(view) => <p>{view} workspace</p>} />);
    expect(screen.getByText("growth workspace")).toBeTruthy();
  });
});
