import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";
import { LAST_WORKSPACE_KEY } from "./workspaceStorage";

describe("WorkspaceShell", () => {
  beforeEach(() => window.localStorage.clear());

  it("owns navigation state and persists the selected workspace", () => {
    render(<WorkspaceShell renderWorkspace={(view) => <p>{view} workspace</p>} />);
    expect(screen.getByRole("main").getAttribute("data-active-workspace")).toBe("home");
    fireEvent.click(screen.getByRole("button", { name: /자료/ }));
    expect(screen.getByText("materials workspace")).toBeTruthy();
    expect(screen.getByRole("main").getAttribute("data-active-workspace")).toBe("materials");
    expect(window.localStorage.getItem(LAST_WORKSPACE_KEY)).toBe("materials");
  });

  it("restores the last valid workspace", () => {
    window.localStorage.setItem(LAST_WORKSPACE_KEY, "growth");
    render(<WorkspaceShell renderWorkspace={(view) => <p>{view} workspace</p>} />);
    expect(screen.getByText("growth workspace")).toBeTruthy();
  });

  it("lets an explicit initial view override persisted state", () => {
    window.localStorage.setItem(LAST_WORKSPACE_KEY, "growth");
    render(<WorkspaceShell initialView="search" renderWorkspace={(view) => <p>{view} workspace</p>} />);
    expect(screen.getByText("search workspace")).toBeTruthy();
  });
});
