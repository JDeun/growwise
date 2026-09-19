import { useEffect, useState, type FormEvent } from "react";

import type { ChildContextLoadState } from "../child-context-state";
import { ChildAvatar, ViewStateNotice } from "../components";
import {
  deleteChildAvatar,
  getHealth,
  setChildAvatar,
  type ChildProfile,
  type GrowthMap,
  type Stage,
} from "../api";
import { stageLabel } from "../presentation";
import "./ChildProfileSection.css";

type ModelOnboardingState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "ready" }
  | { kind: "optional"; configured: boolean };

interface ChildProfileSectionProps {
  connected: boolean;
  children: ChildProfile[];
  activeChild: ChildProfile | null;
  childContext: ChildContextLoadState;
  growthMap: GrowthMap | null;
  activityCount: number;
  nickname: string;
  childStage: Stage;
  birthDate?: string;
  ageMonths: string;
  grade?: string;
  saving: boolean;
  error: string | null;
  onNicknameChange: (value: string) => void;
  onStageChange: (value: Stage) => void;
  onBirthDateChange?: (value: string) => void;
  onAgeMonthsChange: (value: string) => void;
  onGradeChange?: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelectChild: (childId: string) => void;
  onAvatarUpdated?: (child: ChildProfile) => void;
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
  birthDate = "",
  ageMonths,
  grade = "",
  saving,
  error,
  onNicknameChange,
  onStageChange,
  onBirthDateChange = () => undefined,
  onAgeMonthsChange,
  onGradeChange = () => undefined,
  onSubmit,
  onSelectChild,
  onAvatarUpdated,
}: ChildProfileSectionProps) {
  const firstRun = children.length === 0;
  const [modelOnboarding, setModelOnboarding] = useState<ModelOnboardingState>({ kind: "idle" });
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  async function handleAvatarFile(file: File | null) {
    if (!activeChild || !file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setAvatarError("JPG, PNG, WebP 이미지만 사용할 수 있습니다.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setAvatarError("프로필 사진은 15MB 이하로 선택해 주세요.");
      return;
    }

    setAvatarBusy(true);
    setAvatarError(null);
    try {
      const dataBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(reader.error ?? new Error("프로필 사진을 읽지 못했습니다."));
        reader.onload = () => {
          const value = typeof reader.result === "string" ? reader.result : "";
          const comma = value.indexOf(",");
          if (comma < 0) reject(new Error("프로필 사진을 읽지 못했습니다."));
          else resolve(value.slice(comma + 1));
        };
        reader.readAsDataURL(file);
      });
      const updated = await setChildAvatar(activeChild.id, {
        filename: file.name || "avatar",
        mime_type: file.type,
        data_base64: dataBase64,
      });
      onAvatarUpdated?.(updated);
    } catch (cause) {
      setAvatarError(cause instanceof Error ? cause.message : "프로필 사진 저장에 실패했습니다.");
    } finally {
      setAvatarBusy(false);
    }
  }

  async function handleAvatarDelete() {
    if (!activeChild || !activeChild.avatar_asset_id) return;
    setAvatarBusy(true);
    setAvatarError(null);
    try {
      onAvatarUpdated?.(await deleteChildAvatar(activeChild.id));
    } catch (cause) {
      setAvatarError(cause instanceof Error ? cause.message : "프로필 사진 삭제에 실패했습니다.");
    } finally {
      setAvatarBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    if (!firstRun || !connected) {
      setModelOnboarding({ kind: "idle" });
      return () => { cancelled = true; };
    }

    setModelOnboarding({ kind: "checking" });
    void getHealth()
      .then((health) => {
        if (cancelled) return;
        setModelOnboarding(
          health.llm_reachable
            ? { kind: "ready" }
            : { kind: "optional", configured: health.llm_configured },
        );
      })
      .catch(() => {
        if (!cancelled) {
          setModelOnboarding({ kind: "optional", configured: true });
        }
      });

    return () => { cancelled = true; };
  }, [connected, firstRun]);

  return (
    <section className="child-profile-section" aria-labelledby="child-profile-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">아이 프로필</p>
          <h2 id="child-profile-title">{firstRun ? "처음 설정을 마치면 바로 기록을 시작할 수 있습니다." : "아이의 기본 정보와 성장 맥락을 관리합니다."}</h2>
        </div>
        {firstRun && <span className="badge">처음 설정</span>}
      </div>

      {firstRun && (
        <section className="onboarding-panel" aria-label="GrowWise 첫 실행 설정">
          <div className="onboarding-heading">
            <div>
              <p className="card-label">빠른 시작</p>
              <h3>닉네임과 기본 정보만 입력하면 바로 첫 활동을 시작할 수 있습니다.</h3>
            </div>
            <span className="onboarding-optional-badge">AI는 선택 사항</span>
          </div>
          <ol className="onboarding-steps">
            <li className={connected ? "is-complete" : "is-current"}>
              <span className="onboarding-step-number">1</span>
              <div>
                <strong>앱 준비</strong>
                <p>{connected ? "기록을 저장할 준비가 됐습니다." : "앱을 준비하고 있습니다. 잠시 후 자동으로 이어집니다."}</p>
              </div>
            </li>
            <li className={connected ? "is-current" : ""}>
              <span className="onboarding-step-number">2</span>
              <div>
                <strong>첫 아이 프로필 만들기</strong>
                <p>닉네임과 교육 단계만 있으면 됩니다. 월령은 선택입니다.</p>
              </div>
            </li>
            <li className={modelOnboarding.kind === "ready" ? "is-complete" : "is-optional"}>
              <span className="onboarding-step-number">3</span>
              <div>
                <strong>AI 보조 기능 · 선택</strong>
                {modelOnboarding.kind === "checking" ? (
                  <p>AI 보조 기능을 사용할 수 있는지 확인하고 있습니다.</p>
                ) : modelOnboarding.kind === "ready" ? (
                  <p>AI 보조 기능을 사용할 수 있습니다. 기록 정리와 검색, 자료 만들기를 필요할 때 보조합니다.</p>
                ) : (
                  <p>
                    {modelOnboarding.kind === "optional" && modelOnboarding.configured
                      ? "AI 보조 기능이 아직 준비되지 않았습니다."
                      : "AI 보조 기능을 지금 설정하지 않아도 됩니다."}
                    {" "}관찰 기록, 검색, 성장 보기, 활동과 자료 관리는 그대로 사용할 수 있습니다. 나중에 설정에서 사용 가능 상태를 확인할 수 있습니다.
                  </p>
                )}
              </div>
            </li>
          </ol>
          <p className="onboarding-footnote muted">AI 단계는 건너뛰어도 됩니다. 첫 아이를 저장하면 바로 기록을 시작할 수 있습니다.</p>
        </section>
      )}

      {children.length > 0 && (
        <section className="child-roster" aria-labelledby="child-roster-title">
          <div className="child-roster__heading">
            <div>
              <p className="card-label">아이 목록</p>
              <h3 id="child-roster-title">프로필을 선택해 기록 맥락을 바꿉니다.</h3>
            </div>
            <span>{children.length}명</span>
          </div>
          <div className="child-roster__grid">
            {children.map((child) => {
              const selected = child.id === activeChild?.id;
              return (
                <button
                  key={child.id}
                  type="button"
                  className={`child-roster-card ${selected ? "is-active" : ""}`}
                  aria-pressed={selected}
                  onClick={() => onSelectChild(child.id)}
                >
                  <ChildAvatar child={child} size="md" />
                  <span className="child-roster-card__copy">
                    <strong>{child.nickname}</strong>
                    <small>{stageLabel(child.stage)} · {child.age_months ?? "—"}개월</small>
                  </span>
                  <span className="child-roster-card__status" aria-hidden="true">
                    {selected ? "✓" : "›"}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <div className="skeleton-grid child-profile-layout">
        <form className="profile-form" onSubmit={onSubmit}>
          <p className="card-label">{firstRun ? "첫 프로필" : "새 아이 추가"}</p>
          <label>
            <span>아이 닉네임</span>
            <input value={nickname} onChange={(event) => onNicknameChange(event.target.value)} placeholder="예: 샘플아이" maxLength={40} disabled={!connected || saving} />
          </label>
          <label>
            <span>생년월일(권장)</span>
            <input
              type="date"
              value={birthDate}
              onChange={(event) => onBirthDateChange(event.target.value)}
              disabled={!connected || saving}
            />
            <small className="field-help">
              입력하면 월령과 한국 학년을 날짜에 맞춰 자동 계산합니다.
            </small>
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
          <details className="profile-fallback-fields">
            <summary>생년월일 없이 직접 입력</summary>
            <p className="muted">생년월일을 입력했다면 아래 값은 비워 두어도 됩니다.</p>
            <label>
              <span>월령(선택)</span>
              <input type="number" min="0" max="240" value={ageMonths} onChange={(event) => onAgeMonthsChange(event.target.value)} placeholder="예: 108" disabled={!connected || saving || Boolean(birthDate)} />
            </label>
            {["elementary", "middle", "high"].includes(childStage) && (
              <label>
                <span>현재 학년(선택)</span>
                <input type="number" min="1" max="12" value={grade} onChange={(event) => onGradeChange(event.target.value)} placeholder="초1=1 · 중1=7 · 고1=10" disabled={!connected || saving || Boolean(birthDate)} />
              </label>
            )}
          </details>
          <button className="primary-button" type="submit" disabled={!connected || saving}>
            {saving ? "저장 중…" : firstRun ? "첫 프로필 저장" : "새 프로필 저장"}
          </button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>

        <article className="verification-card child-profile-card">
          {activeChild ? (
            <>
              <div className="child-profile-card__identity">
                <div className="child-profile-card__avatar">
                  <ChildAvatar child={activeChild} size="lg" />
                  <label className="child-avatar-edit">
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      disabled={avatarBusy}
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0] ?? null;
                        void handleAvatarFile(file);
                        event.currentTarget.value = "";
                      }}
                    />
                    <span>{avatarBusy ? "처리 중…" : activeChild.avatar_asset_id ? "사진 변경" : "사진 추가"}</span>
                  </label>
                </div>
                <div>
                  <p className="card-label">현재 아이</p>
                  <h3>{activeChild.nickname}</h3>
                  <p className="muted">{stageLabel(activeChild.stage)} · {activeChild.age_months ?? "—"}개월</p>
                  {activeChild.avatar_asset_id && (
                    <button
                      type="button"
                      className="child-avatar-remove"
                      disabled={avatarBusy}
                      onClick={() => void handleAvatarDelete()}
                    >
                      사진 삭제
                    </button>
                  )}
                </div>
              </div>
              {avatarError && <p className="form-error" role="alert">{avatarError}</p>}
              <dl className="verification-list">
                <div><dt>월령</dt><dd>{activeChild.age_months ?? "-"}개월</dd></div>
                <div><dt>최근 기록</dt><dd>{childContext.growth.kind === "ready" && growthMap ? growthMap.total_logs_in_period : "—"}</dd></div>
                <div><dt>활동</dt><dd>{childContext.activities.kind === "ready" ? activityCount : "—"}</dd></div>
              </dl>
            </>
          ) : (
            <>
              <p className="card-label">첫 단계</p>
              <h3>첫 아이 프로필을 만들어 주세요.</h3>
              <p className="muted">개인 식별정보 대신 앱 안에서 구분할 닉네임만 사용해도 됩니다.</p>
            </>
          )}
        </article>
      </div>

      {!activeChild && connected && !firstRun && (
        <section className="child-context-required">
          <ViewStateNotice
            kind="empty"
            title="먼저 아이 프로필을 만들어 주세요."
            description="관찰, 성장, 활동, 자료, 검색 화면은 선택한 아이의 기록을 기준으로 동작합니다."
          />
        </section>
      )}
    </section>
  );
}
