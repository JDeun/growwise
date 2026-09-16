import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ActivitiesSection } from "./ActivitiesSection";

const plans = [
  {
    id: "activity-1",
    child_id: "child-1",
    title: "고양이 그림책 읽기",
    status: "active" as const,
    source_refs: [],
    parent_note: null,
    started_at: "2026-09-15T09:00:00+09:00",
    completed_at: null,
    skipped_at: null,
  },
  {
    id: "activity-2",
    child_id: "child-1",
    title: "블록 쌓기",
    status: "completed" as const,
    source_refs: ["material:material-1"],
    parent_note: null,
    started_at: "2026-09-14T09:00:00+09:00",
    completed_at: "2026-09-14T09:30:00+09:00",
    skipped_at: null,
  },
];

describe("ActivitiesSection", () => {
  it("shows the activity lifecycle and result-data affordance without quest pressure language", () => {
    const html = renderToStaticMarkup(
      <ActivitiesSection
        suggestions={null}
        suggestionsLoading={false}
        error={null}
        planBusy={false}
        plans={plans}
        loadState={{ kind: "ready" }}
        onLoadSuggestions={vi.fn()}
        onSaveActivity={vi.fn()}
        onTransition={vi.fn()}
        onRetryPlans={vi.fn()}
      />,
    );

    expect(html).toContain("활동 목록");
    expect(html).toContain("내 활동");
    expect(html).toContain("생성됨");
    expect(html).toContain("진행 중");
    expect(html).toContain("완료됨");
    expect(html).toContain("결과 기록됨");
    expect(html).toContain("생성 자료");
    expect(html).toContain("고양이 그림책 읽기 활동 진행 상태");
    expect(html).toContain(">생성<");
    expect(html).toContain(">진행<");
    expect(html).toContain(">완료<");
    expect(html).toContain(">결과<");
    expect(html).toContain("결과 기록 확인 중");
    expect(html).not.toContain("QUEST BOARD");
    expect(html).not.toContain("활동 퀘스트");
  });
});
