import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  getGrowthMap,
  listActivities,
  listBackups,
  listMaterials,
  listObservations,
  listResources,
  type ActivityPlan,
  type BackupItem,
  type ChildProfile,
  type GeneratedMaterial,
  type GrowthMap,
  type LearningLog,
  type ResourceRecord,
} from "../api";
import { ChildAvatar } from "../components/ChildAvatar";
import type { WorkspaceView } from "../components/workspaceTypes";
import { stageLabel } from "../presentation";
import "./HomeDashboard.css";

type DashboardData = {
  child: ChildProfile;
  growthMap: GrowthMap | null;
  observations: LearningLog[];
  activities: ActivityPlan[];
  materials: GeneratedMaterial[];
  resources: ResourceRecord[];
  backups: BackupItem[];
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

function relativeBackupLabel(item: BackupItem | undefined): string {
  if (!item) return "백업 없음";
  const timestamp = Date.parse(item.modified_at);
  if (!Number.isFinite(timestamp)) return "최근 백업";
  const hours = Math.max(0, Math.floor((Date.now() - timestamp) / 3_600_000));
  if (hours < 1) return "방금 전";
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

export function HomeDashboard({ active, onNavigate }: HomeDashboardProps) {
  const {
    activeChild,
    children,
    selectChild,
    syncRememberedChild,
  } = useActiveChild();
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
        listBackups(),
      ]);
      if (currentRequest !== requestId.current) return;

      const [
        growthResult,
        observationsResult,
        activitiesResult,
        materialsResult,
        resourcesResult,
        backupsResult,
      ] = results;
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
          backups: backupsResult.status === "fulfilled" ? backupsResult.value : [],
          failedDomains: results.filter((result) => result.status === "rejected").length,
        },
      });
    } catch (error) {
      if (currentRequest !== requestId.current) return;
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "대시보드를 불러오지 못했습니다.",
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
        <div className="dashboard-skeleton" role="status" aria-live="polite">
          <div />
          <div />
          <div />
          <span>아이의 최근 기록을 정리하고 있습니다.</span>
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="home-dashboard" aria-labelledby="home-dashboard-title">
        <div className="home-dashboard-error" role="alert">
          <strong>대시보드를 불러오지 못했습니다.</strong>
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
      <section className="home-dashboard home-dashboard--empty" aria-labelledby="home-dashboard-title">
        <span className="dashboard-empty-mark" aria-hidden="true">G</span>
        <p className="eyebrow">WELCOME TO GROWWISE</p>
        <h2 id="home-dashboard-title">첫 아이 프로필을 만들면 대시보드가 시작됩니다.</h2>
        <p>관찰, 사진, 학습 기록과 활동을 한 아이의 맥락으로 연결합니다.</p>
        <button className="primary-button" type="button" onClick={() => onNavigate("observations")}>
          아이 프로필 만들기
        </button>
      </section>
    );
  }

  const { data } = state;
  const activeActivities = data.activities.filter((activity) => activity.status === "active");
  const pendingMaterials = data.materials.filter((material) =>
    ["draft", "review_pending", "revision_requested"].includes(material.status),
  );
  const recentObservations = data.observations.slice(0, 4);
  const recentCount = data.growthMap?.total_logs_in_period ?? data.observations.length;
  const latestBackup = [...data.backups].sort(
    (left, right) => Date.parse(right.modified_at) - Date.parse(left.modified_at),
  )[0];

  const suggestions = [
    {
      kicker: "기록",
      title: recentCount === 0 ? "첫 관찰을 남겨보세요" : "오늘의 관찰을 이어가세요",
      body: recentCount === 0
        ? "짧은 한 문장으로 시작해도 충분합니다."
        : `최근 ${data.growthMap?.period_days ?? 30}일 동안 ${recentCount}개의 기록이 쌓였습니다.`,
      view: "observations" as WorkspaceView,
    },
    {
      kicker: "활동",
      title: activeActivities.length > 0 ? "진행 중인 활동이 있습니다" : "새 활동을 살펴보세요",
      body: activeActivities.length > 0
        ? `${activeActivities.length}개의 활동을 이어서 기록할 수 있습니다.`
        : "아이의 최근 맥락을 바탕으로 활동 후보를 확인합니다.",
      view: "activities" as WorkspaceView,
    },
    {
      kicker: "AI 자료",
      title: pendingMaterials.length > 0 ? "검토할 학습자료가 있습니다" : "새 학습자료 만들기",
      body: pendingMaterials.length > 0
        ? `${pendingMaterials.length}개의 초안 또는 수정본을 부모가 검토할 차례입니다.`
        : "저장한 근거 자료를 바탕으로 초안을 만듭니다.",
      view: "materials" as WorkspaceView,
    },
  ];

  return (
    <section className="home-dashboard" aria-labelledby="home-dashboard-title">
      <header className="dashboard-hero">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h2 id="home-dashboard-title">{data.child.nickname}의 오늘을 한눈에 보세요.</h2>
          <p>기록은 가볍게, 연결은 GrowWise가 정리합니다.</p>
        </div>
        <button className="dashboard-refresh" type="button" onClick={() => void load()}>
          <span aria-hidden="true">↻</span>
          새로고침
        </button>
      </header>

      {data.failedDomains > 0 ? (
        <p className="home-dashboard-warning" role="status">
          일부 영역 {data.failedDomains}개를 불러오지 못해 확인 가능한 기록만 표시합니다.
        </p>
      ) : null}

      <section className="dashboard-children" aria-labelledby="dashboard-children-title">
        <div className="dashboard-section-heading">
          <div>
            <h3 id="dashboard-children-title">아이 프로필</h3>
            <span>{children.length}명</span>
          </div>
          <button type="button" onClick={() => onNavigate("observations")}>프로필 관리</button>
        </div>
        <div className="dashboard-child-list">
          {children.map((child) => {
            const selected = child.id === data.child.id;
            return (
              <button
                key={child.id}
                type="button"
                className={`dashboard-child-card ${selected ? "is-active" : ""}`}
                onClick={() => selectChild(child.id)}
                aria-pressed={selected}
              >
                <ChildAvatar child={child} size="lg" />
                <span className="dashboard-child-copy">
                  <strong>{child.nickname}</strong>
                  <small>{stageLabel(child.stage)} · {child.age_months ?? "—"}개월</small>
                </span>
                {selected ? <span className="dashboard-current-chip">현재</span> : null}
              </button>
            );
          })}
          <button
            type="button"
            className="dashboard-child-card dashboard-child-card--add"
            onClick={() => onNavigate("observations")}
          >
            <span className="dashboard-add-avatar" aria-hidden="true">+</span>
            <span className="dashboard-child-copy">
              <strong>아이 추가</strong>
              <small>새 프로필 만들기</small>
            </span>
          </button>
        </div>
      </section>

      <div className="home-metrics" aria-label="현재 요약">
        <article>
          <span className="metric-icon metric-icon--green" aria-hidden="true">●</span>
          <div><small>최근 기록</small><strong>{recentCount}</strong><p>최근 {data.growthMap?.period_days ?? 30}일</p></div>
        </article>
        <article>
          <span className="metric-icon metric-icon--blue" aria-hidden="true">●</span>
          <div><small>진행 중 활동</small><strong>{activeActivities.length}</strong><p>이어갈 수 있는 활동</p></div>
        </article>
        <article>
          <span className="metric-icon metric-icon--amber" aria-hidden="true">●</span>
          <div><small>검토할 자료</small><strong>{pendingMaterials.length}</strong><p>초안·검토·수정 요청</p></div>
        </article>
        <article>
          <span className="metric-icon metric-icon--violet" aria-hidden="true">●</span>
          <div><small>백업 상태</small><strong className="metric-backup">{relativeBackupLabel(latestBackup)}</strong><p>{data.backups.length}개 보관</p></div>
        </article>
      </div>

      <div className="home-dashboard-grid">
        <section className="home-recent" aria-labelledby="home-recent-title">
          <div className="dashboard-section-heading">
            <div>
              <h3 id="home-recent-title">최근 활동</h3>
              <span>Learning timeline</span>
            </div>
            <button type="button" onClick={() => onNavigate("learning")}>전체 보기</button>
          </div>
          {recentObservations.length === 0 ? (
            <p className="home-recent-empty">아직 기록이 없습니다. 오늘의 한 문장부터 시작해 보세요.</p>
          ) : (
            <div className="home-recent-list">
              {recentObservations.map((log) => (
                <article key={log.id}>
                  <span className="home-timeline-dot" aria-hidden="true" />
                  <div>
                    <strong>{log.title || "관찰 기록"}</strong>
                    <p>{log.parent_observation}</p>
                    <small>
                      {log.created_at
                        ? new Date(log.created_at).toLocaleString("ko-KR", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "기록 시각 없음"}
                    </small>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="home-next-actions" aria-labelledby="home-next-actions-title">
          <div className="dashboard-section-heading">
            <div>
              <h3 id="home-next-actions-title">오늘의 제안</h3>
              <span>Next steps</span>
            </div>
          </div>
          <div className="home-action-list">
            {suggestions.map((item, index) => (
              <button key={item.kicker} type="button" onClick={() => onNavigate(item.view)}>
                <span className={`suggestion-index suggestion-index--${index + 1}`}>{index + 1}</span>
                <span className="suggestion-copy">
                  <small>{item.kicker}</small>
                  <strong>{item.title}</strong>
                  <p>{item.body}</p>
                </span>
                <span className="suggestion-arrow" aria-hidden="true">→</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
