import type { FormEvent } from "react";

import type { ChildContextLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { ChildProfile, GrowthMap, Stage } from "../api";
import { stageLabel } from "../presentation";

interface ChildProfileSectionProps {
  connected: boolean;
  children: ChildProfile[];
  activeChild: ChildProfile | null;
  childContext: ChildContextLoadState;
  growthMap: GrowthMap | null;
  activityCount: number;
  nickname: string;
  childStage: Stage;
  ageMonths: string;
  saving: boolean;
  error: string | null;
  onNicknameChange: (value: string) => void;
  onStageChange: (value: Stage) => void;
  onAgeMonthsChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelectChild: (childId: string) => void;
}

export function ChildProfileSection({
  connected,
  children,
  activeChild,
  childContext,
  growthMap,
  activityCount,
  nickname,
  childStage,
  ageMonths,
  saving,
  error,
  onNicknameChange,
  onStageChange,
  onAgeMonthsChange,
  onSubmit,
  onSelectChild,
}: ChildProfileSectionProps) {
  return (
    <>
      <div className="section-heading">
        <div>
          <p className="eyebrow">CHILD CONTEXT</p>
          <h2>기존 기록을 이어서 사용합니다.</h2>
        </div>
        <span className="badge">Pre-alpha</span>
      </div>

      {children.length > 0 && (
        <div className="child-switcher">
          <label>
            <span>아이 선택</span>
            <select value={activeChild?.id ?? ""} onChange={(event) => onSelectChild(event.target.value)}>
              {children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.nickname} · {stageLabel(child.stage)} · {child.age_months ?? "-"}개월
                </option>
              ))}
            </select>
          </label>
          <p className="muted">마지막 선택을 기억하지만 데이터는 항상 Core에서 다시 조회합니다.</p>
        </div>
      )}

      <div className="skeleton-grid">
        <form className="profile-form" onSubmit={onSubmit}>
          <p className="card-label">NEW CHILD</p>
          <label>
            <span>아이 닉네임</span>
            <input value={nickname} onChange={(event) => onNicknameChange(event.target.value)} placeholder="예: 샘플아이" maxLength={40} disabled={!connected || saving} />
          </label>
          <label>
            <span>교육 단계</span>
            <select value={childStage} onChange={(event) => onStageChange(event.target.value as Stage)} disabled={!connected || saving}>
              <option value="infant_0_2">영아 0~2세</option>
              <option value="preschool_3_5">유아 3~5세</option>
              <option value="elementary">초등</option>
              <option value="middle">중등</option>
              <option value="high">고등</option>
            </select>
          </label>
          <label>
            <span>월령(선택)</span>
            <input type="number" min="0" max="240" value={ageMonths} onChange={(event) => onAgeMonthsChange(event.target.value)} placeholder="예: 108" disabled={!connected || saving} />
          </label>
          <button className="primary-button" type="submit" disabled={!connected || saving}>
            {saving ? "저장 중…" : "새 프로필 저장"}
          </button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>

        <article className="verification-card">
          {activeChild ? (
            <>
              <p className="card-label">ACTIVE CONTEXT</p>
              <h3>{activeChild.nickname}</h3>
              <p className="muted">프로필은 선택 즉시 유지하고, 각 기록 영역은 Core에서 독립적으로 다시 불러옵니다.</p>
              <dl className="verification-list">
                <div><dt>월령</dt><dd>{activeChild.age_months ?? "-"}개월</dd></div>
                <div><dt>최근 기록</dt><dd>{childContext.growth.kind === "ready" && growthMap ? growthMap.total_logs_in_period : "—"}</dd></div>
                <div><dt>활동</dt><dd>{childContext.activities.kind === "ready" ? activityCount : "—"}</dd></div>
              </dl>
            </>
          ) : (
            <>
              <p className="card-label">EMPTY</p>
              <h3>아이 프로필을 만들어 주세요.</h3>
            </>
          )}
        </article>
      </div>

      {!activeChild && connected && (
        <section className="child-context-required">
          <ViewStateNotice
            kind="empty"
            title="먼저 아이 프로필을 만들어 주세요."
            description="관찰, 성장, 활동, 자료, 검색 작업공간은 선택한 아이의 기록 범위 안에서 동작합니다."
          />
        </section>
      )}
    </>
  );
}
