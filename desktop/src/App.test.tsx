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

    expect(html).toContain("앱 상태");
    expect(html).toContain("AI 보조 기능");
    expect(html).toContain("홈에서 첫 아이 프로필을 만들면");
    expect(html).toContain("설정");
    expect(html).toContain("가족 설정");
    expect(html).toContain("개인정보와 삭제");
    expect(html).not.toContain("AI와 대화하기");
    expect(html).not.toContain("새 활동 후보");
    expect(html).not.toContain("참고 자료 추가");
    expect(html).not.toContain("Personal Education OS");
    expect(html).not.toContain("LOCAL-FIRST");
    expect(html).not.toContain("GrowWise Core");
    expect(html).not.toContain("ollama pull");
  });
});
