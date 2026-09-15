import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { OperationNotice } from "./OperationNotice";

describe("OperationNotice", () => {
  it("renders nothing without a message", () => {
    expect(renderToStaticMarkup(<OperationNotice message={null} onDismiss={vi.fn()} />)).toBe("");
  });

  it("announces successful writes politely", () => {
    const html = renderToStaticMarkup(
      <OperationNotice message="관찰 기록을 저장했습니다." onDismiss={vi.fn()} />,
    );
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain('aria-atomic="true"');
    expect(html).toContain("관찰 기록을 저장했습니다.");
    expect(html).toContain('aria-label="알림 닫기"');
  });
});
