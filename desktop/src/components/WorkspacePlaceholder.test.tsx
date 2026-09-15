import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspacePlaceholder } from "./WorkspacePlaceholder";

describe("WorkspacePlaceholder", () => {
  it("uses the registered workspace label", () => {
    render(<WorkspacePlaceholder view="search" />);
    expect(screen.getByRole("heading", { name: "검색" })).toBeTruthy();
  });
});
