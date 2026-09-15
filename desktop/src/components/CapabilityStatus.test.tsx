import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CapabilityStatus } from "./CapabilityStatus";

describe("CapabilityStatus", () => {
  it("announces its initial health check without implying a failure", () => {
    const html = renderToStaticMarkup(<CapabilityStatus />);
    expect(html).toContain("GrowWise 상태를 확인하고 있습니다.");
    expect(html).toContain('role="status"');
    expect(html).not.toContain("연결을 확인해 주세요");
  });
});
