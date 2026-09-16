import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  getGrowthMap,
  listActivities,
  listMaterials,
  listObservations,
  listResources,
  type ActivityPlan,
  type ChildProfile,
  type GeneratedMaterial,
  type GrowthMap,
  type LearningLog,
  type ResourceRecord,
} from "../api";
import type { WorkspaceView } from "../components/workspaceTypes";
import "./HomeDashboard.css";

type DashboardData = {
  child: ChildProfile;
  growthMap: GrowthMap | null;
  observations: LearningLog[];
  activities: ActivityPlan[];
  materials: GeneratedMaterial[];
  resources: ResourceRecord[];
  failedDomains: number;
};

type DashboardState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: DashboardData };

interface HomeDashboardProps {
  active: boolean;
  onNavigate: (view: WorkspaceView) => void;
}

function newestFirst(left: LearningLog, right: LearningLog): number {
  const leftTime = left.created_at ? Date.parse(left.created_at) : 0;
  const rightTime = right.created_at ? Date.parse(right.created_at) : 0;
  return rightTime - leftTime;
}

export function HomeDashboard({ active, onNavigate }: HomeDashboardProps) {
  const { activeChild, syncRememberedChild } = useActiveChild();
  const [state, setState] = useState<DashboardState>({ kind: "idle" });
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    if (!activeChild) {
      setState({ kind: "empty" });
      return;
    }
    setState({ kind: "loading" });

    try {
      const child = activeChild;
      const results = await Promise.allSettled([
        getGrowthMap(child.id),
        listObservations(child.id),
        listActivities(child.id),
        listMaterials(child.id),
        listResources(child.id),
      ]);
      if (currentRequest !== requestId.current) return;

      const [growthResult, observationsResult, activitiesResult, materialsResult, resourcesResult] = results;
      setState({
        kind: "ready",
        data: {
          child,
          growthMap: growthResult.status === "fulfilled" ? growthResult.value : null,
          observations:
            observationsResult.status === "fulfilled"
              ? [...observationsResult.value].sort(newestFirst)
              : [],
          activities: activitiesResult.status === "fulfilled" ? activitiesResult.value : [],
          materials: materialsResult.status === "fulfilled" ? materialsResult.value : [],
          resources: resourcesResult.status === "fulfilled" ? resourcesResult.value : [],
          failedDomains: results.filter((result) => result.status === "rejected").length,
        },
      });
    } catch (error) {
      if (currentRequest !== requestId.current) return;
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "홈 요약을 불러오지 못했습니다.",
      });
    }
  }, [activeChild]);

  useEffect(() => {
    if (!active) {
      requestId.current += 1;
      return;
    }
    syncRememberedChild();
  }, [active, syncRememberedChild]);

  useEffect(() => {
    if (!active) return;
    void load();
  }, [active, load]);

  if (!active) return null;

  if (state.kind === "loading" || state.kind === "idle") {
    return (
      <section className="home-dashboard" aria-labelledby="home-dashboard-title">
        <div className="home-dashboard-heading">
          <div>
            <p className="eyebrow">TODAY</p>
            <h2 id="home-dashboard-title">오늘의 GrowWise</h2>
          </div>
        </div>
        <div className="home-dashboard-loading" role="status" aria-live="polite">
          최근 기록과 다음 행동을 정리하고 있습니다.
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="home-dashboard" aria-labelledby="home-dashboard-title">
        <div className="home-dashboard-heading">
          <div>
            <p className="eyebrow">TODAY</p>
            <h2 id="home-dashboard-title">오늘의 GrowWise</h2>
          </div>
        </div>
        <div className="home-dashboard-error" role="alert">
          <strong>홈 요약을 불러오지 못했습니다.</strong>
          <span>{state.message}</span>
          <button className="quiet-button" type="button" onClick={() => void load()}>
            다시 시도
          </button>
        </div>
      </section>
    );
  }

  if (state.kind === "empty") {
    return (
      <section className="home-dashboard" aria-labelledby="home-dashboard-title">
        <div className="home-dashboard-heading">
          <div>
            <p className="eyebrow">START HERE</p>
            <h2 id="home-dashboard-title">아이 프로필부터 시작해 주세요.</h2>
            <p>프로필을 만들면 관찰, 활동, 성장 맥락과 학습 자료를 한 화면에서 이어 볼 수 있습니다.</p>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={() => document.querySelector<HTMLInputElement>(".profile-form input")?.focus()}
          >
            프로필 입력으로 이동
          </button>
        </div>
      </section>
    );
  }

  const { data } = state;
  const activeActivities = data.activities.filter((activity) => activity.status === "active");
  const pendingMaterials = data.materials.filter((material) =>
    ["draft", "review_pending", "revision_requested"].includes(material.status),
  );
  const recentObservations = data.observations.slice(0, 3);
  const recentCount = data.growthMap?.total_logs_in_period ?? data.observations.length;

  return (
    <section className="home-dashboard" aria-labelledby="home-dashboard-title">
      <div className="home-dashboard-heading">
        <div>
          <p className="eyebrow">TODAY · {data.child.nickname}</p>
          <h2 id="home-dashboard-title">다음에 할 일을 바로 이어가세요.</h2>
          <p>최근 기록을 기준으로 자주 쓰는 작업만 앞에 둡니다.</p>
        </div>
        <button className="quiet-button" type="button" onClick={() => void load()}>
          요약 새로고침
        </button>
      </div>

      {data.failedDomains > 0 && (
        <p className="home-dashboard-warning" role="status">
          일부 영역 {data.failedDomains}개를 불러오지 못해 확인 가능한 기록만 표시합니다.
        </p>
      )}

      <div className="home-metrics" aria-label="현재 요약">
        <article><span>최근 관찰</span><strong>{recentCount}</strong><small>최근 {data.growthMap?.period_days ?? 30}일</small></article>
        <article><span>진행 중 활동</span><strong>{activeActivities.length}</strong><small>이어갈 수 있는 활동</small></article>
        <article><span>검토할 자료</span><strong>{pendingMaterials.length}</strong><small>초안·검토·수정 요청</small></article>
        <article><span>라이브러리</span><strong>{data.resources.length}</strong><small>연결된 자료</small></article>
      </div>

      <div className="home-dashboard-grid">
        <section className="home-next-actions" aria-labelledby="home-next-actions-title">
          <div className="home-section-heading">
            <h3 id="home-next-actions-title">다음 행동</h3>
            <span>추천이 아니라 빠른 진입점입니다.</span>
          </div>
          <div className="home-action-list">
            <button type="button" onClick={() => onNavigate("observations")}>
              <span>관찰</span>
              <strong>{recentCount === 0 ? "첫 관찰 남기기" : "새 관찰 기록하기"}</strong>
              <small>오늘 의미 있었던 순간을 짧게 남깁니다.</small>
            </button>
            <button type="button" onClick={() => onNavigate("activities")}>
              <span>활동</span>
              <strong>{activeActivities.length > 0 ? `진행 중 활동 ${activeActivities.length}건 이어가기` : "활동 후보 살펴보기"}</strong>
              <small>선택한 활동만 저장하고 상태를 이어갑니다.</small>
            </button>
            <button type="button" onClick={() => onNavigate("materials")}>
              <span>자료</span>
              <strong>{pendingMaterials.length > 0 ? `검토할 자료 ${pendingMaterials.length}건 확인` : "새 학습 자료 만들기"}</strong>
              <small>생성 결과는 Parent Review를 거쳐 확정합니다.</small>
            </button>
            <button type="button" onClick={() => onNavigate("library")}>
              <span>라이브러리</span>
              <strong>{data.resources.length > 0 ? `자료 ${data.resources.length}건 찾아보기` : "첫 참고 자료 저장하기"}</strong>
              <small>책, 메모, 교육과정, 웹 자료를 연결합니다.</small>
            </button>
          </div>
        </section>

        <section className="home-recent" aria-labelledby="home-recent-title">
          <div className="home-section-heading">
            <h3 id="home-recent-title">최근 관찰</h3>
            <button type="button" onClick={() => onNavigate("observations")}>전체 보기</button>
          </div>
          {recentObservations.length === 0 ? (
            <p className="home-recent-empty">아직 관찰 기록이 없습니다. 기록 공백은 실패가 아닙니다.</p>
          ) : (
            <div className="home-recent-list">
              {recentObservations.map((log) => (
                <article key={log.id}>
                  <p>{log.parent_observation}</p>
                  <small>
                    {log.created_at
                      ? new Date(log.created_at).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })
                      : "기록 시각 없음"}
                  </small>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
