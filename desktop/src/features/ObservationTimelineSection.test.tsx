import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ObservationTimelineSection } from "./ObservationTimelineSection";

const timeline = [
  {
    id: "log-1",
    child_id: "child-1",
    activity_plan_id: "activity-1",
    parent_observation: "고양이 그림을 오래 바라봤다.",
    tags: ["그림책"],
    experience_axes: ["reading" as const],
    interest: "고양이",
    next_activity: "고양이 소리 흉내내기",
    created_at: "2026-09-15T09:00:00+09:00",
  },
];

const activities = [
  {
    id: "activity-1",
    child_id: "child-1",
    title: "고양이 그림책 읽기",
    status: "active" as const,
    source_refs: [],
    parent_note: null,
    started_at: null,
    completed_at: null,
    skipped_at: null,
  },
];

describe("ObservationTimelineSection", () => {
  it("renders client-side filters and a detail affordance for loaded records", () => {
    const html = renderToStaticMarkup(
      <ObservationTimelineSection
        loadState={{ kind: "ready" }}
        timeline={timeline}
        activityPlans={activities}
        onRetry={vi.fn()}
      />,
    );

    expect(html).toContain("관찰 기록 필터");
    expect(html).toContain("기록 검색");
    expect(html).toContain("경험 축");
    expect(html).toContain("활동 연결");
    expect(html).toContain("전체 기간");
    expect(html).toContain("조건에 맞는 관찰 1건");
    expect(html).toContain("상세 보기");
    expect(html).toContain("고양이 그림을 오래 바라봤다.");
  });
});
