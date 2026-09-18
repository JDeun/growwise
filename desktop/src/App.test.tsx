import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import App from "./App";
import { ActiveChildProvider } from "./active-child-context";

describe("App feature composition", () => {
  it("renders the settings controller surface with first-run guidance", () => {
    const html = renderToStaticMarkup(
      <ActiveChildProvider>
        <App activeView="settings" />
      </ActiveChildProvider>,
    );

    expect(html).toContain("GrowWise");
    expect(html).toContain("아이의 배움 기록");
    expect(html).toContain("앱 상태");
    expect(html).toContain("AI 보조 기능");
    expect(html).toContain("첫 아이 프로필을 만들어 주세요.");
    expect(html).toContain("설정");
    expect(html).toContain("가족 설정");
    expect(html).toContain("개인정보와 삭제");
    expect(html).not.toContain("Personal Education OS");
    expect(html).not.toContain("LOCAL-FIRST");
    expect(html).not.toContain("GrowWise Core");
    expect(html).not.toContain("ollama pull");
  });
});
