import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CapabilityBanner } from "./CapabilityBanner";

describe("CapabilityBanner", () => {
  it("explains that deterministic features remain available without AI", () => {
    const html = renderToStaticMarkup(
      <CapabilityBanner connected llmConfigured={false} llmReachable={false} />,
    );
    expect(html).toContain("기본 기능은 정상적으로 사용할 수 있습니다.");
    expect(html).toContain("기록, 검색, 성장 맵, 활동, 자료 관리와 부모 검토");
    expect(html).toContain('role="status"');
  });

  it("separates a GrowWise connection failure from an AI-only failure", () => {
    const html = renderToStaticMarkup(
      <CapabilityBanner connected={false} llmConfigured={false} llmReachable={false} />,
    );
    expect(html).toContain("GrowWise 연결을 확인해 주세요.");
    expect(html).toContain("저장된 데이터는 그대로 유지됩니다.");
  });

  it("states that AI is enhancement rather than a dependency", () => {
    const html = renderToStaticMarkup(
      <CapabilityBanner connected llmConfigured llmReachable />,
    );
    expect(html).toContain("AI 보강을 사용할 수 있습니다.");
    expect(html).toContain("AI 없이도 동작");
  });
});
