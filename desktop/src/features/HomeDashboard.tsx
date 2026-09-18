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
import { ChildAvatar } from "../components";
import type { WorkspaceView } from "../components/workspaceTypes";
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

export function HomeDashboard({ active, onNavigate }: HomeDashboardProps) {
  const { activeChild, children, syncRememberedChild } = useActiveChild();
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
            <p className="eyebrow">오늘</p>
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
            <p className="eyebrow">오늘</p>
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
            <p className="eyebrow">처음 시작</p>
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
  const latestBackup = [...data.backups].sort(
    (left, right) => Date.parse(right.modified_at) - Date.parse(left.modified_at),
  )[0] ?? null;
  const backupLabel = latestBackup
    ? new Date(latestBackup.modified_at).toLocaleDateString("ko-KR", {
        month: "short",
        day: "numeric",
      })
    : "없음";

  const recommendation: {
    view: WorkspaceView;
    category: string;
    title: string;
    description: string;
  } = activeActivities.length > 0
    ? {
        view: "activities",
        category: "이어가기",
        title: `진행 중 활동 ${activeActivities.length}건을 이어가 보세요`,
        description: "아이의 반응을 살피며 다음 단계까지 자연스럽게 연결할 수 있습니다.",
      }
    : pendingMaterials.length > 0
      ? {
          view: "materials",
          category: "부모 검토",
          title: `검토할 학습 자료 ${pendingMaterials.length}건이 있어요`,
          description: "AI가 만든 자료를 확인하고 우리 아이에게 맞는 내용만 선택해 주세요.",
        }
      : recentCount === 0
        ? {
            view: "observations",
            category: "첫 기록",
            title: "오늘의 작은 발견을 첫 관찰로 남겨보세요",
            description: "짧은 한 문장만 남겨도 이후 활동과 성장 맥락을 연결하는 시작점이 됩니다.",
          }
        : {
            view: "activities",
            category: "추천 활동",
            title: "최근 기록에서 이어갈 활동을 살펴보세요",
            description: "관심사와 최근 기록을 바탕으로 집에서 바로 이어갈 수 있는 활동을 확인합니다.",
          };

  return (
    <section className="home-dashboard" aria-labelledby="home-dashboard-title">
      <div className="home-dashboard-heading home-dashboard-heading--concept">
        <div>
          <h2 id="home-dashboard-title">대시보드</h2>
          <p>오늘도 소중한 성장의 순간을 함께 해요.</p>
        </div>
        <div className="home-dashboard-date" aria-label="오늘 날짜">
          <span>
            {new Date().toLocaleDateString("ko-KR", {
              year: "numeric",
              month: "long",
              day: "numeric",
              weekday: "short",
            })}
          </span>
          <strong>좋은 하루예요!</strong>
        </div>
      </div>

      {data.failedDomains > 0 && (
        <p className="home-dashboard-warning" role="status">
          일부 영역 {data.failedDomains}개를 불러오지 못해 확인 가능한 기록만 표시합니다.
        </p>
      )}

      <div className="home-metrics" aria-label="현재 요약">
        <article className="home-metric-card">
          <span className="home-metric-icon" aria-hidden="true">◎</span>
          <div>
            <span>등록된 아이</span>
            <strong>{children.length}명</strong>
            <small>{children.map((child) => child.nickname).slice(0, 2).join(", ") || data.child.nickname}</small>
          </div>
        </article>
        <article className="home-metric-card">
          <span className="home-metric-icon home-metric-icon--blue" aria-hidden="true">▣</span>
          <div>
            <span>최근 학습 기록</span>
            <strong>{recentCount}건</strong>
            <small>최근 {data.growthMap?.period_days ?? 30}일 기준</small>
          </div>
        </article>
        <article className="home-metric-card">
          <span className="home-metric-icon home-metric-icon--violet" aria-hidden="true">✦</span>
          <div>
            <span>AI 추천 활동</span>
            <strong>{activeActivities.length}개</strong>
            <small>{activeActivities.length > 0 ? "진행 중인 활동 기준" : "새 활동을 확인해 보세요"}</small>
          </div>
        </article>
        <article className="home-metric-card home-metric-card--backup">
          <span className="home-metric-icon" aria-hidden="true">◆</span>
          <div>
            <span>백업 상태</span>
            <strong>{latestBackup ? "정상" : "확인 필요"}</strong>
            <small>{latestBackup ? `최근 백업: ${backupLabel}` : "첫 백업을 만들어 주세요"}</small>
          </div>
        </article>
      </div>

      <div className="home-dashboard-grid">
        <section className="home-recent" aria-labelledby="home-recent-title">
          <div className="home-section-heading">
            <h3 id="home-recent-title">최근 활동</h3>
            <button type="button" onClick={() => onNavigate("observations")}>더보기 ›</button>
          </div>
          {recentObservations.length === 0 ? (
            <p className="home-recent-empty">아직 기록이 없습니다. 오늘의 작은 발견부터 남겨보세요.</p>
          ) : (
            <div className="home-recent-list">
              {recentObservations.map((log, index) => (
                <article key={log.id}>
                  <span className="home-recent-icon" aria-hidden="true">{index === 0 ? "✦" : index === 1 ? "●" : "■"}</span>
                  <div>
                    <p>{log.parent_observation}</p>
                    <small>
                      {log.created_at
                        ? new Date(log.created_at).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })
                        : "기록 시각 없음"}
                    </small>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="home-next-actions" aria-labelledby="home-next-actions-title">
          <div className="home-section-heading">
            <h3 id="home-next-actions-title">오늘의 추천 활동</h3>
            <button type="button" onClick={() => onNavigate("activities")}>모두 보기 ›</button>
          </div>
          <article className="home-recommendation-card">
            <div className="home-recommendation-visual" aria-hidden="true">
              <img src="/growwise-symbol.svg" alt="" />
            </div>
            <div className="home-recommendation-copy">
              <span>{recommendation.category}</span>
              <h4>{recommendation.title}</h4>
              <p>{recommendation.description}</p>
              <div className="home-recommendation-tags" aria-hidden="true">
                <span>관찰 연결</span>
                <span>부모 확인</span>
                <span>우리 아이 맞춤</span>
              </div>
              <button type="button" className="primary-button" onClick={() => onNavigate(recommendation.view)}>
                자세히 보기 →
              </button>
            </div>
          </article>
        </section>
      </div>
      </div>
    </section>
  );
}
