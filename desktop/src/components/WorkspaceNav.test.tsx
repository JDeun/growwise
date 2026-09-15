import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceNav } from "./WorkspaceNav";

describe("WorkspaceNav", () => {
  it("marks the active workspace and emits navigation changes", () => {
    const onChange = vi.fn();
    render(<WorkspaceNav activeView="home" onChange={onChange} />);

    expect(screen.getByRole("button", { name: /홈/ }).getAttribute("aria-current")).toBe("page");

    fireEvent.click(screen.getByRole("button", { name: /자료/ }));
    expect(onChange).toHaveBeenCalledWith("materials");
  });
});
