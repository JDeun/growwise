import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceFrame } from "./WorkspaceFrame";

describe("WorkspaceFrame", () => {
  it("provides a labelled boundary for migrated content", () => {
    render(<WorkspaceFrame view="materials"><p>material content</p></WorkspaceFrame>);
    expect(screen.getByRole("heading", { name: "자료" })).toBeTruthy();
    expect(screen.getByText("material content")).toBeTruthy();
  });
});
