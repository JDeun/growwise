import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ActiveChildProvider } from "../active-child-context";
import { childContextState } from "../child-context-state";
import type { ChildProfile } from "../api";
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

    expect(markup).toContain('id="child-profile-title">첫 아이 프로필 만들기</h2>');
    expect(markup).toContain("닉네임과 교육 단계만 있으면 됩니다. 생년월일은 선택입니다.");
    expect(markup).toContain("첫 프로필 저장");
    expect(markup.indexOf("첫 프로필 저장")).toBeLessThan(markup.indexOf('class="onboarding-optional"'));
    expect(markup).not.toContain("onboarding-steps");
    expect(markup).not.toContain("verification-card");
  });

  it("prefers birth date while keeping manual age and grade as optional fallback", () => {
    const markup = renderFirstRun();

    expect(markup).toContain("생년월일(권장)");
    expect(markup).toContain("생년월일 없이 직접 입력");
    expect(markup).toContain('type="date"');
    expect(markup).not.toContain("학년은 반드시");
  });

  it("keeps AI optional without exposing implementation setup commands", () => {
    const markup = renderFirstRun();

    expect(markup).toContain("AI 보조 기능 · 선택");
    expect(markup).toContain('<details class="onboarding-optional"><summary>');
    expect(markup).toContain("AI 없이도 기록과 기본 활동 자료를 사용할 수 있습니다");
    expect(markup).toContain("나중에 설정에서 AI 보조 기능을 준비할 수 있습니다");
    expect(markup).not.toContain("Core-only");
    expect(markup).not.toContain("ollama serve");
    expect(markup).not.toContain("ollama pull");
  });

  it("explains why first-profile saving is unavailable while connecting", () => {
    const markup = renderFirstRun(false);

    expect(markup).toContain('role="status">앱을 준비하고 있습니다. 연결되면 프로필을 저장할 수 있습니다.');
    expect(markup).toContain('type="submit" disabled="">첫 프로필 저장');
  });
});



describe("ChildProfileSection product profile layout", () => {
  it("renders child cards, active profile detail, and avatar controls", () => {
    const children: ChildProfile[] = [
      {
        id: "child-a",
        nickname: "수아",
        stage: "preschool_3_5",
        age_months: 42,
        interests: [],
        avatar_asset_id: null,
      },
      {
        id: "child-b",
        nickname: "민준",
        stage: "elementary",
        age_months: 96,
        interests: [],
        avatar_asset_id: null,
      },
    ];

    const markup = renderToStaticMarkup(
      <ActiveChildProvider>
        <ChildProfileSection
          connected
          children={children}
          activeChild={children[0]}
          childContext={childContextState("ready")}
          growthMap={null}
          activityCount={2}
          nickname=""
          childStage="preschool_3_5"
          ageMonths=""
          saving={false}
          error={null}
          onNicknameChange={() => undefined}
          onStageChange={() => undefined}
          onAgeMonthsChange={() => undefined}
          onSubmit={() => undefined}
          onSelectChild={() => undefined}
          onAvatarUpdated={() => undefined}
        />
      </ActiveChildProvider>,
    );

    expect(markup).toContain('aria-labelledby="child-roster-title"');
    expect(markup).toContain("프로필을 선택해 기록 맥락을 바꿉니다");
    expect(markup).toContain("수아");
    expect(markup).toContain("민준");
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain("사진 추가");
    expect(markup).toContain("최근 기록");
    expect(markup).toContain("활동");
  });
});
