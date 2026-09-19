import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspacePlaceholder } from "./WorkspacePlaceholder";

describe("WorkspacePlaceholder", () => {
  it("uses registered workspace metadata", () => {
    const html = renderToStaticMarkup(<WorkspacePlaceholder view="search" />);
    expect(html).toContain("기록 검색");
    expect(html).toContain("기록을 검색하고 근거를 확인합니다.");
  });
});
