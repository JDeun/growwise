import { useState, type ReactNode } from "react";

import { useActiveChild } from "../active-child-context";
import { ChildAvatar } from "../components";
import { stageLabel } from "../presentation";
import type { WorkspaceView } from "../components/workspaceTypes";
import "./ProfileWorkspaceHub.css";

type ProfileTab = "records" | "development" | "report";

interface ProfileWorkspaceHubProps {
  app: ReactNode;
  renderLearning: (active: boolean) => ReactNode;
  onNavigate: (view: WorkspaceView) => void;
}

const TABS: Array<{ value: ProfileTab; label: string }> = [
  { value: "records", label: "학습 기록" },
  { value: "development", label: "발달 분석" },
  { value: "report", label: "성장 리포트" },
];

export function ProfileWorkspaceHub({
  app,
  renderLearning,
  onNavigate,
}: ProfileWorkspaceHubProps) {
  const { children, activeChild, activeChildId, selectChild } = useActiveChild();
  const [tab, setTab] = useState<ProfileTab>("records");
  const [managing, setManaging] = useState(false);
  const showManage = managing || !activeChild;

  return (
    <section
      className={`profile-hub${showManage ? " is-managing" : ""}`}
      data-profile-tab={tab}
      aria-labelledby="profile-hub-title"
    >
      <header className="profile-hub-heading">
        <div>
          <p className="eyebrow">CHILD PROFILE</p>
          <h1 id="profile-hub-title">아이 프로필</h1>
          <p>우리 아이의 특별한 성장과 배움의 흐름을 한곳에서 살펴봅니다.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => onNavigate("learning")}>
          <span aria-hidden="true">＋</span>
          새 기록 추가
        </button>
      </header>

      {showManage ? (
        <div className="profile-manage-view">
          {activeChild && (
            <div className="profile-manage-toolbar">
              <button className="quiet-button" type="button" onClick={() => setManaging(false)}>
                ← 프로필로 돌아가기
              </button>
            </div>
          )}
          <div className="profile-hub-core">{app}</div>
        </div>
      ) : (
        <div className="profile-hub-layout">
          <aside className="profile-summary-card" aria-label="현재 아이 요약">
            <ChildAvatar child={activeChild} size="lg" />
            <div className="profile-summary-identity">
              <h2>{activeChild.nickname}</h2>
              <p>
                {stageLabel(activeChild.stage)}
                {activeChild.age_months !== null ? ` · ${activeChild.age_months}개월` : ""}
              </p>
            </div>

            {children.length > 1 && (
              <label className="profile-child-switcher">
                <span>아이 전환</span>
                <select value={activeChildId} onChange={(event) => selectChild(event.target.value)}>
                  {children.map((child) => (
                    <option value={child.id} key={child.id}>{child.nickname}</option>
                  ))}
                </select>
              </label>
            )}

            <button className="quiet-button profile-edit-button" type="button" onClick={() => setManaging(true)}>
              프로필 관리
            </button>

            <div className="profile-summary-section">
              <span>좋아하는 것</span>
              <div className="profile-summary-tags">
                {activeChild.interests.length > 0
                  ? activeChild.interests.slice(0, 6).map((interest) => <em key={interest}>{interest}</em>)
                  : <small>아직 등록된 관심사가 없습니다.</small>}
              </div>
            </div>

            <div className="profile-summary-section">
              <span>최근 학습 목표</span>
              {(activeChild.learning_goals ?? []).length > 0 ? (
                <ul>
                  {(activeChild.learning_goals ?? []).slice(0, 3).map((goal) => <li key={goal}>{goal}</li>)}
                </ul>
              ) : (
                <small>설정에서 학습 목표를 추가할 수 있습니다.</small>
              )}
            </div>

            <div className="profile-summary-section">
              <span>부모 메모</span>
              <p>{activeChild.notes?.trim() || "아이를 이해하는 데 필요한 메모를 남겨보세요."}</p>
            </div>

            <button className="profile-settings-link" type="button" onClick={() => onNavigate("settings")}>
              상세 설정 열기 →
            </button>
          </aside>

          <section className="profile-content-card">
            <div className="profile-content-tabs" role="tablist" aria-label="아이 프로필 보기">
              {TABS.map((item) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === item.value}
                  className={tab === item.value ? "is-active" : ""}
                  key={item.value}
                  onClick={() => setTab(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="profile-records-slot">
              {renderLearning(tab === "records")}
            </div>

            <div className="profile-hub-core">
              {app}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
