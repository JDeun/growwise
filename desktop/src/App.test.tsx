import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import App from "./App";
import { ActiveChildProvider } from "./active-child-context";

describe("App feature composition", () => {
  it("renders the controller shell with user-facing first-run guidance", () => {
    const html = renderToStaticMarkup(
      <ActiveChildProvider>
        <App />
      </ActiveChildProvider>,
    );
    expect(html).toContain("GrowWise");
    expect(html).toContain("아이의 배움 기록");
    expect(html).toContain("기록 · 연결 · 활용");
    expect(html).toContain("앱 상태");
    expect(html).toContain("AI 보조 기능");
    expect(html).toContain("첫 아이 프로필을 만들어 주세요.");
    expect(html).toContain("AI는 선택 사항");
    expect(html).toContain("내 데이터");
    expect(html).not.toContain("Personal Education OS");
    expect(html).not.toContain("LOCAL-FIRST");
    expect(html).not.toContain("GrowWise Core");
    expect(html).not.toContain("ollama pull");
  });
});
