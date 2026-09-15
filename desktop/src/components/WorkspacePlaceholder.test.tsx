import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkspacePlaceholder } from "./WorkspacePlaceholder";

describe("WorkspacePlaceholder", () => {
  it("uses registered workspace metadata", () => {
    const html = renderToStaticMarkup(<WorkspacePlaceholder view="search" />);
    expect(html).toContain("검색");
    expect(html).toContain("아이의 기록과 후속 질문을 탐색합니다.");
  });
});
