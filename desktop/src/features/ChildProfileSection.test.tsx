import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ActiveChildProvider } from "../active-child-context";
import { childContextState } from "../child-context-state";
import { ChildProfileSection } from "./ChildProfileSection";

function renderFirstRun(connected = true) {
  return renderToStaticMarkup(
    <ActiveChildProvider>
      <ChildProfileSection
        connected={connected}
        children={[]}
        activeChild={null}
        childContext={childContextState("idle")}
        growthMap={null}
        activityCount={0}
        nickname=""
        childStage="infant_0_2"
        ageMonths=""
        saving={false}
        error={null}
        onNicknameChange={() => undefined}
        onStageChange={() => undefined}
        onAgeMonthsChange={() => undefined}
        onSubmit={() => undefined}
        onSelectChild={() => undefined}
      />
    </ActiveChildProvider>,
  );
}

describe("ChildProfileSection first-run onboarding", () => {
  it("frames the first child as the only required setup", () => {
    const markup = renderFirstRun();

    expect(markup).toContain("2-MINUTE SETUP");
    expect(markup).toContain("필수 설정은 첫 아이 프로필 하나뿐입니다");
    expect(markup).toContain("FIRST CHILD");
    expect(markup).toContain("첫 프로필 저장");
  });

  it("keeps local AI explicitly optional", () => {
    const markup = renderFirstRun();

    expect(markup).toContain("AI 선택 사항");
    expect(markup).toContain("로컬 AI 보강 연결 · 선택");
    expect(markup).toContain("Core-only");
    expect(markup).toContain("ollama serve");
    expect(markup).toContain("ollama pull qwen3.5:9b");
  });
});
