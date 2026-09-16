import { useEffect, useMemo, useState } from "react";

import type { ViewLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { ActivityPlan, ExperienceAxis, LearningLog } from "../api";
import { AXIS_OPTIONS } from "../presentation";
import "./ObservationTimelineSection.css";

interface ObservationTimelineSectionProps {
  loadState: ViewLoadState;
  timeline: LearningLog[];
  activityPlans: ActivityPlan[];
  onRetry: () => void;
}

type ActivityFilter = "all" | "linked" | "unlinked";
type PeriodFilter = "all" | "7" | "30";

function timestamp(log: LearningLog): number {
  if (!log.created_at) return 0;
  const value = Date.parse(log.created_at);
  return Number.isNaN(value) ? 0 : value;
}

function axisName(axis: ExperienceAxis): string {
  return AXIS_OPTIONS.find((item) => item.value === axis)?.label ?? axis;
}

export function ObservationTimelineSection({
  loadState,
  timeline,
  activityPlans,
  onRetry,
}: ObservationTimelineSectionProps) {
  const [query, setQuery] = useState("");
  const [axis, setAxis] = useState<ExperienceAxis | "all">("all");
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>("all");
  const [period, setPeriod] = useState<PeriodFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filteredTimeline = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR");
    const periodDays = period === "all" ? null : Number(period);
    const cutoff = periodDays ? Date.now() - periodDays * 24 * 60 * 60 * 1000 : null;

    return [...timeline]
      .sort((left, right) => timestamp(right) - timestamp(left))
      .filter((log) => {
        if (axis !== "all" && !log.experience_axes.includes(axis)) return false;
        if (activityFilter === "linked" && !log.activity_plan_id) return false;
        if (activityFilter === "unlinked" && log.activity_plan_id) return false;
        if (cutoff !== null && timestamp(log) < cutoff) return false;
        if (!normalizedQuery) return true;

        const linkedActivity = log.activity_plan_id
          ? activityPlans.find((item) => item.id === log.activity_plan_id)
          : null;
        const searchable = [
          log.parent_observation,
          log.interest ?? "",
          log.next_activity ?? "",
          log.tags.join(" "),
          log.experience_axes.map(axisName).join(" "),
          linkedActivity?.title ?? "",
        ]
          .join(" ")
          .toLocaleLowerCase("ko-KR");
        return searchable.includes(normalizedQuery);
      });
  }, [activityFilter, activityPlans, axis, period, query, timeline]);

  useEffect(() => {
    if (selectedId && !filteredTimeline.some((log) => log.id === selectedId)) {
      setSelectedId(null);
    }
  }, [filteredTimeline, selectedId]);

  const selectedLog = selectedId ? timeline.find((log) => log.id === selectedId) ?? null : null;
  const selectedActivity = selectedLog?.activity_plan_id
    ? activityPlans.find((activity) => activity.id === selectedLog.activity_plan_id) ?? null
    : null;
  const filtersActive = query.trim() || axis !== "all" || activityFilter !== "all" || period !== "all";

  function clearFilters() {
    setQuery("");
    setAxis("all");
    setActivityFilter("all");
    setPeriod("all");
  }

  return (
    <section className="timeline-section">
      <div className="activity-heading">
        <div>
          <p className="card-label">OBSERVATION TIMELINE</p>
          <h3>관찰 기록</h3>
        </div>
        <span className="badge">
          {loadState.kind === "ready" ? `${filteredTimeline.length}/${timeline.length}건` : "확인 중"}
        </span>
      </div>

      {loadState.kind === "loading" && (
        <ViewStateNotice
          kind="loading"
          title="관찰 기록을 불러오는 중입니다."
          description="이 아이의 기록만 확인합니다."
        />
      )}
      {loadState.kind === "error" && (
        <ViewStateNotice
          kind="error"
          title="관찰 기록을 불러오지 못했습니다."
          description={loadState.message}
          action={
            <button className="quiet-button" type="button" onClick={onRetry}>
              다시 시도
            </button>
          }
        />
      )}
      {loadState.kind === "ready" && timeline.length === 0 && (
        <ViewStateNotice
          kind="empty"
          title="아직 기록이 없습니다."
          description="기록 공백은 실패가 아닙니다. 의미 있는 순간이 있을 때만 남겨도 됩니다."
        />
      )}

      {loadState.kind === "ready" && timeline.length > 0 && (
        <>
          <div className="timeline-filters" aria-label="관찰 기록 필터">
            <label className="timeline-filter-search">
              <span>기록 검색</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="관찰 내용, 관심, 태그, 활동 검색"
              />
            </label>
            <label>
              <span>경험 축</span>
              <select value={axis} onChange={(event) => setAxis(event.target.value as ExperienceAxis | "all")}>
                <option value="all">전체</option>
                {AXIS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>활동 연결</span>
              <select value={activityFilter} onChange={(event) => setActivityFilter(event.target.value as ActivityFilter)}>
                <option value="all">전체</option>
                <option value="linked">활동 연결됨</option>
                <option value="unlinked">일반 관찰</option>
              </select>
            </label>
            <label>
              <span>기간</span>
              <select value={period} onChange={(event) => setPeriod(event.target.value as PeriodFilter)}>
                <option value="all">전체 기간</option>
                <option value="7">최근 7일</option>
                <option value="30">최근 30일</option>
              </select>
            </label>
            {filtersActive && (
              <button className="quiet-button timeline-filter-reset" type="button" onClick={clearFilters}>
                필터 초기화
              </button>
            )}
          </div>

          <p className="timeline-filter-status" role="status" aria-live="polite">
            조건에 맞는 관찰 {filteredTimeline.length}건
          </p>

          {filteredTimeline.length === 0 ? (
            <ViewStateNotice
              kind="empty"
              title="조건에 맞는 관찰이 없습니다."
              description="검색어나 필터를 넓혀 다시 확인해 보세요. 원본 기록은 변경되지 않습니다."
              action={
                <button className="quiet-button" type="button" onClick={clearFilters}>
                  전체 기록 보기
                </button>
              }
            />
          ) : (
            <div className="timeline-browser">
              <div className="timeline-list">
                {filteredTimeline.map((log) => {
                  const linkedActivity = log.activity_plan_id
                    ? activityPlans.find((item) => item.id === log.activity_plan_id)
                    : null;
                  const selected = selectedId === log.id;
                  return (
                    <article key={log.id} className={`timeline-card ${selected ? "selected" : ""}`}>
                      <button
                        className="timeline-card-open"
                        type="button"
                        aria-expanded={selected}
                        aria-controls={`timeline-detail-${log.id}`}
                        onClick={() => setSelectedId(selected ? null : log.id)}
                      >
                        {linkedActivity && (
                          <small className="timeline-activity">활동 · {linkedActivity.title}</small>
                        )}
                        <p>{log.parent_observation}</p>
                        <div className="axis-summary">
                          {log.experience_axes.map((item) => (
                            <span key={item}>{axisName(item)}</span>
                          ))}
                        </div>
                        {log.created_at && (
                          <time dateTime={log.created_at}>
                            {new Date(log.created_at).toLocaleString("ko-KR")}
                          </time>
                        )}
                        <span className="timeline-card-detail-label">
                          {selected ? "상세 닫기" : "상세 보기"}
                        </span>
                      </button>
                    </article>
                  );
                })}
              </div>

              {selectedLog && (
                <aside
                  className="timeline-detail"
                  id={`timeline-detail-${selectedLog.id}`}
                  aria-labelledby="timeline-detail-title"
                >
                  <div className="timeline-detail-heading">
                    <div>
                      <p className="card-label">RECORD DETAIL</p>
                      <h4 id="timeline-detail-title">관찰 상세</h4>
                    </div>
                    <button className="quiet-button" type="button" onClick={() => setSelectedId(null)}>
                      닫기
                    </button>
                  </div>
                  <p className="timeline-detail-observation">{selectedLog.parent_observation}</p>
                  <dl className="timeline-detail-list">
                    <div>
                      <dt>기록 시각</dt>
                      <dd>
                        {selectedLog.created_at
                          ? new Date(selectedLog.created_at).toLocaleString("ko-KR")
                          : "기록 시각 없음"}
                      </dd>
                    </div>
                    <div>
                      <dt>연결 활동</dt>
                      <dd>{selectedActivity?.title ?? "일반 관찰"}</dd>
                    </div>
                    <div>
                      <dt>경험 축</dt>
                      <dd>
                        {selectedLog.experience_axes.length > 0
                          ? selectedLog.experience_axes.map(axisName).join(", ")
                          : "연결 없음"}
                      </dd>
                    </div>
                    <div>
                      <dt>관심</dt>
                      <dd>{selectedLog.interest ?? "기록 없음"}</dd>
                    </div>
                    <div>
                      <dt>태그</dt>
                      <dd>{selectedLog.tags.length > 0 ? selectedLog.tags.join(", ") : "기록 없음"}</dd>
                    </div>
                    <div>
                      <dt>다음 활동 메모</dt>
                      <dd>{selectedLog.next_activity ?? "기록 없음"}</dd>
                    </div>
                  </dl>
                </aside>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
