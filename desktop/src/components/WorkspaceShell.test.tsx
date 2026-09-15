import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./WorkspaceShell";

describe("WorkspaceShell", () => {
  it("owns navigation state and renders the selected workspace", () => {
    render(<WorkspaceShell renderWorkspace={(view) => <p>{view} workspace</p>} />);

    expect(screen.getByText("home workspace")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /자료/ }));
    expect(screen.getByText("materials workspace")).toBeTruthy();
  });
});
