import { describe, expect, it } from "vitest";

import { materialReadingMarkdown } from "./material-reading-view";

const published = `# 민들레 관찰

> GrowWise 활동 자료 · 부모가 내용을 확인한 뒤 사용합니다.

## 오늘의 목표
- 목표: 씨앗의 움직임을 관찰합니다.
- 교육과정 연결: 자연탐구
- 적용 교육과정: 2022 개정 교육과정
- 기준 고시: 교육부 고시
- 결과보다 관찰 과정에 집중합니다.

## 예상 시간
- 15분 · 더 짧게 끝내도 됩니다.

## 준비물
- 종이, 색연필

## 단계별 활동 기준
- 학습 수준: 실제 관찰과 설명
- 자료 유형 기준: 질문부터 확장까지

## 활동 자료
1. 씨앗을 자세히 보고 생김새를 그립니다.
2. 바람에 어떻게 움직일지 예측합니다.
- 교육과정 연결: 이 줄은 아이가 직접 적은 활동 내용입니다.

## 막힐 때 힌트
- 손으로 먼저 움직여 보세요.

## 돌아보기
- 예측과 실제 움직임은 어떻게 달랐나요?

## 더 해보기
- 다른 씨앗과 비교합니다.
`;

describe("standard material reading view", () => {
  it("keeps infant safety instructions visible before the activity", () => {
    const infant = published.replace("## 활동 자료", "## 활동 전 안전\n보호자가 곁에서 지켜보고 작은 부품과 끈은 치웁니다.\n\n## 활동 자료");
    const visible = materialReadingMarkdown(infant);
    expect(visible).toContain("## 활동 전 안전");
    expect(visible).toContain("작은 부품과 끈은 치웁니다");
    expect(visible).not.toContain("## 단계별 활동 기준");
  });
  it("removes only publication metadata and stage criteria before the actual activities", () => {
    const original = published;
    const visible = materialReadingMarkdown(published);
    expect(visible).not.toContain("- 교육과정 연결: 자연탐구");
    expect(visible).not.toContain("- 적용 교육과정:");
    expect(visible).not.toContain("- 기준 고시:");
    expect(visible).not.toContain("## 단계별 활동 기준");
    expect(visible).not.toContain("- 학습 수준:");
    expect(visible).not.toContain("- 자료 유형 기준:");
    for (const text of ["씨앗의 움직임을 관찰", "15분", "종이, 색연필", "씨앗을 자세히 보고", "손으로 먼저", "예측과 실제", "다른 씨앗과 비교", "이 줄은 아이가 직접"]) {
      expect(visible).toContain(text);
    }
    expect(published).toBe(original);
  });

  it("leaves ordinary custom Markdown and partial lookalikes byte-for-byte unchanged", () => {
    const ordinary = published.replace("> GrowWise 활동 자료 · 부모가 내용을 확인한 뒤 사용합니다.", "> 부모가 직접 만든 활동 자료");
    expect(materialReadingMarkdown(ordinary)).toBe(ordinary);
    const incomplete = published.replace("## 활동 자료", "## 나의 활동");
    expect(materialReadingMarkdown(incomplete)).toBe(incomplete);
    const quotedMarker = published.replace("> GrowWise 활동 자료", "> > GrowWise 활동 자료");
    expect(materialReadingMarkdown(quotedMarker)).toBe(quotedMarker);
    const fencedExample = "```markdown\n" + published + "\n```";
    expect(materialReadingMarkdown(fencedExample)).toBe(fencedExample);
  });

  it("preserves similarly named sections inside the learner's activity core", () => {
    const customCore = published.replace("1. 씨앗을", "## 단계별 활동 기준\n- 내가 정한 활동 기준\n\n1. 씨앗을");
    expect(materialReadingMarkdown(customCore)).toContain("## 단계별 활동 기준\n- 내가 정한 활동 기준");
  });
});
