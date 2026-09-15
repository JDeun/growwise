import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ViewStateNotice } from "./ViewStateNotice";

describe("ViewStateNotice", () => {
  it("announces loading and empty states politely", () => {
    const html = renderToStaticMarkup(
      <ViewStateNotice kind="loading" title="불러오는 중" description="기록을 확인합니다." />,
    );
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
  });

  it("announces errors immediately and renders recovery actions", () => {
    const html = renderToStaticMarkup(
      <ViewStateNotice
        kind="error"
        title="불러오지 못했습니다"
        description="다시 시도해 주세요."
        action={<button type="button">다시 시도</button>}
      />,
    );
    expect(html).toContain('role="alert"');
    expect(html).toContain("다시 시도");
  });
});
