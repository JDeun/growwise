import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  readRememberedChildId,
  useActiveChild,
  writeRememberedChildId,
} from "../active-child-context";
import { deleteChild, updateChild, type BackupItem, type Stage } from "../api";
import "./DataManagementSection.css";

interface DataManagementSectionProps {
  connected: boolean;
  backups: BackupItem[];
  busy: boolean;
  error: string | null;
  notice: string | null;
  onImport: () => void;
  onCreate: () => void;
  onExport: (archiveName: string) => void;
  onRestore: (archiveName: string) => void;
}

export function parseProfileList(value: string): string[] {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

export function parseLearningGoals(value: string): string[] {
  return [...new Set(value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean))];
}

export function DataManagementSection({
  connected,
  backups,
  busy,
  error,
  notice,
  onImport,
  onCreate,
  onExport,
  onRestore,
}: DataManagementSectionProps) {
  const { children, activeChild, upsertChild } = useActiveChild();
  const [profileChildId, setProfileChildId] = useState(activeChild?.id ?? children[0]?.id ?? "");
  const [profileNickname, setProfileNickname] = useState("");
  const [profileStage, setProfileStage] = useState<Stage>("infant_0_2");
  const [profileAgeMonths, setProfileAgeMonths] = useState("");
  const [profileInterests, setProfileInterests] = useState("");
  const [profilePrimaryLanguage, setProfilePrimaryLanguage] = useState("ko-KR");
  const [profileAdditionalLanguages, setProfileAdditionalLanguages] = useState("");
  const [profileLearningGoals, setProfileLearningGoals] = useState("");
  const [profileNotes, setProfileNotes] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileNotice, setProfileNotice] = useState<string | null>(null);
  const [deleteChildId, setDeleteChildId] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [privacyBusy, setPrivacyBusy] = useState(false);
  const [privacyError, setPrivacyError] = useState<string | null>(null);

  const selectedProfileChild = useMemo(
    () => children.find((child) => child.id === profileChildId) ?? null,
    [children, profileChildId],
  );
  const selectedDeleteChild = useMemo(
    () => children.find((child) => child.id === deleteChildId) ?? null,
    [children, deleteChildId],
  );

  useEffect(() => {
    const fallbackId = activeChild?.id ?? children[0]?.id ?? "";
    setProfileChildId((current) =>
      current && children.some((child) => child.id === current) ? current : fallbackId,
    );
  }, [activeChild?.id, children]);

  useEffect(() => {
    if (!selectedProfileChild) {
      setProfileNickname("");
      setProfileStage("infant_0_2");
      setProfileAgeMonths("");
      setProfileInterests("");
      setProfilePrimaryLanguage("ko-KR");
      setProfileAdditionalLanguages("");
      setProfileLearningGoals("");
      setProfileNotes("");
      return;
    }
    setProfileNickname(selectedProfileChild.nickname);
    setProfileStage(selectedProfileChild.stage);
    setProfileAgeMonths(
      selectedProfileChild.age_months === null ? "" : String(selectedProfileChild.age_months),
    );
    setProfileInterests(selectedProfileChild.interests.join(", "));
    setProfilePrimaryLanguage(selectedProfileChild.primary_language || "ko-KR");
    setProfileAdditionalLanguages((selectedProfileChild.additional_languages ?? []).join(", "));
    setProfileLearningGoals((selectedProfileChild.learning_goals ?? []).join("\n"));
    setProfileNotes(selectedProfileChild.notes ?? "");
  }, [selectedProfileChild]);

  const destructiveBusy = busy || privacyBusy || profileBusy;
  const deletionConfirmed =
    selectedDeleteChild !== null && deleteConfirmation.trim() === selectedDeleteChild.nickname;

  function handleProfileChildChange(childId: string) {
    setProfileChildId(childId);
    setProfileError(null);
    setProfileNotice(null);
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProfileChild || profileBusy || !connected) return;

    const nickname = profileNickname.trim();
    if (!nickname) {
      setProfileError("아이 닉네임을 입력해 주세요.");
      return;
    }

    const ageText = profileAgeMonths.trim();
    const ageMonths = ageText === "" ? null : Number(ageText);
    if (
      ageMonths !== null
      && (!Number.isInteger(ageMonths) || ageMonths < 0 || ageMonths > 240)
    ) {
      setProfileError("월령은 0~240 사이의 정수로 입력해 주세요.");
      return;
    }

    const primaryLanguage = profilePrimaryLanguage.trim();
    if (primaryLanguage.length < 2) {
      setProfileError("주 사용 언어를 두 글자 이상 입력해 주세요.");
      return;
    }

    setProfileBusy(true);
    setProfileError(null);
    setProfileNotice(null);
    try {
      const updated = await updateChild(selectedProfileChild.id, {
        nickname,
        stage: profileStage,
        age_months: ageMonths,
        interests: parseProfileList(profileInterests),
        primary_language: primaryLanguage,
        additional_languages: parseProfileList(profileAdditionalLanguages),
        learning_goals: parseLearningGoals(profileLearningGoals),
        notes: profileNotes.trim() || null,
      });
      upsertChild(updated);
      setProfileNotice("아이 프로필을 저장했습니다. 최신 정보로 화면을 갱신합니다.");
      // App still owns a legacy child-state projection alongside ActiveChildContext. Reloading
      // after this low-frequency settings mutation keeps every child-scoped view consistent
      // with the authoritative store until that duplicate state is fully removed.
      window.setTimeout(() => window.location.reload(), 0);
    } catch (profileSaveError) {
      setProfileError(
        profileSaveError instanceof Error && profileSaveError.message.trim()
          ? profileSaveError.message
          : "아이 프로필 저장에 실패했습니다.",
      );
    } finally {
      setProfileBusy(false);
    }
  }

  async function handleDeleteChild() {
    if (!selectedDeleteChild || !deletionConfirmed || destructiveBusy) return;
    setPrivacyBusy(true);
    setPrivacyError(null);
    try {
      await deleteChild(selectedDeleteChild.id);
      // Storage cleanup is best-effort only. A restricted WebView must not turn a successful
      // server-side purge into a misleading deletion error.
      try {
        const storage = window.localStorage;
        if (readRememberedChildId(storage) === selectedDeleteChild.id) {
          writeRememberedChildId(storage, "");
        }
      } catch {
        // The full reload below will rebuild child selection from the authoritative store.
      }
      // A full reload deliberately discards every in-memory child-scoped view/request after purge.
      window.location.reload();
    } catch (deleteError) {
      setPrivacyError(
        deleteError instanceof Error && deleteError.message.trim()
          ? deleteError.message
          : "아이 데이터 삭제에 실패했습니다.",
      );
      setPrivacyBusy(false);
    }
  }

  return (
    <section className="data-management-section">
      <section className="profile-management-zone" aria-labelledby="profile-management-title">
        <div className="activity-heading">
          <div>
            <p className="card-label">가족 설정</p>
            <h2 id="profile-management-title">아이 프로필 관리</h2>
            <p className="muted">
              아이를 선택해 표시 정보와 학습 맥락을 수정합니다. 실제 식별정보보다는 앱 안에서 필요한 최소 정보만 저장하는 것을 권장합니다.
            </p>
          </div>
        </div>

        {children.length === 0 ? (
          <p className="muted">홈에서 첫 아이 프로필을 만들면 여기에서 수정하고 관리할 수 있습니다.</p>
        ) : (
          <form className="profile-management-form" onSubmit={(event) => void handleSaveProfile(event)}>
            <div className="field-grid">
              <label>
                관리할 아이
                <select
                  value={profileChildId}
                  onChange={(event) => handleProfileChildChange(event.target.value)}
                  disabled={!connected || destructiveBusy}
                >
                  {children.map((child) => (
                    <option key={child.id} value={child.id}>{child.nickname}</option>
                  ))}
                </select>
              </label>
              <label>
                아이 닉네임
                <input
                  value={profileNickname}
                  onChange={(event) => setProfileNickname(event.target.value)}
                  maxLength={120}
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
              </label>
              <label>
                교육 단계
                <select
                  value={profileStage}
                  onChange={(event) => setProfileStage(event.target.value as Stage)}
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                >
                  <option value="infant_0_2">영아 0~2세</option>
                  <option value="preschool_3_5">유아 3~5세</option>
                  <option value="elementary">초등</option>
                  <option value="middle">중등</option>
                  <option value="high">고등</option>
                </select>
              </label>
              <label>
                월령(선택)
                <input
                  type="number"
                  min="0"
                  max="240"
                  value={profileAgeMonths}
                  onChange={(event) => setProfileAgeMonths(event.target.value)}
                  placeholder="영유아 중심으로 사용"
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
              </label>
              <label className="field-span">
                관심사(선택)
                <input
                  value={profileInterests}
                  onChange={(event) => setProfileInterests(event.target.value)}
                  placeholder="예: 공룡, 그림책, 만들기"
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
                <span className="field-help">쉼표로 구분합니다.</span>
              </label>
              <label>
                주 사용 언어
                <input
                  value={profilePrimaryLanguage}
                  onChange={(event) => setProfilePrimaryLanguage(event.target.value)}
                  maxLength={35}
                  placeholder="예: ko-KR"
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
              </label>
              <label>
                추가 사용 언어(선택)
                <input
                  value={profileAdditionalLanguages}
                  onChange={(event) => setProfileAdditionalLanguages(event.target.value)}
                  placeholder="예: 영어, 일본어"
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
              </label>
              <label className="field-span">
                학습 목표(선택)
                <textarea
                  value={profileLearningGoals}
                  onChange={(event) => setProfileLearningGoals(event.target.value)}
                  rows={3}
                  placeholder={"한 줄에 하나씩 적습니다.\n예: 읽은 내용을 자기 말로 설명하기"}
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
              </label>
              <label className="field-span">
                부모 메모(선택)
                <textarea
                  value={profileNotes}
                  onChange={(event) => setProfileNotes(event.target.value)}
                  rows={3}
                  maxLength={10000}
                  placeholder="자료나 활동을 고를 때 참고할 맥락만 간단히 남겨 주세요."
                  disabled={!selectedProfileChild || !connected || destructiveBusy}
                />
              </label>
            </div>
            {profileError && <p className="form-error" role="alert">{profileError}</p>}
            {profileNotice && <p className="muted" role="status" aria-live="polite">{profileNotice}</p>}
            <div className="review-actions profile-management-actions">
              <button
                className="primary-button"
                type="submit"
                disabled={!selectedProfileChild || !connected || destructiveBusy}
              >
                {profileBusy ? "저장 중…" : "프로필 변경 저장"}
              </button>
            </div>
            <p className="muted profile-management-footnote">새 아이 추가는 홈의 ‘아이 프로필’ 영역에서 할 수 있습니다.</p>
          </form>
        )}
      </section>

      <div className="activity-heading data-section-divider">
        <div>
          <p className="card-label">내 데이터</p>
          <h2>백업과 복원</h2>
          <p className="muted">
            기록을 하나의 백업 파일로 보관할 수 있습니다. 복원하면 저장된 기록을 기준으로 검색 데이터도 다시 준비합니다.
          </p>
        </div>
        <div className="review-actions">
          <button className="quiet-button" type="button" onClick={onImport} disabled={!connected || destructiveBusy}>
            백업 파일 가져오기
          </button>
          <button className="quiet-button" type="button" onClick={onCreate} disabled={!connected || destructiveBusy}>
            {busy ? "처리 중…" : "지금 백업"}
          </button>
        </div>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="muted" role="status" aria-live="polite">{notice}</p>}
      {backups.length === 0 ? (
        <p className="muted">아직 만든 백업이 없습니다.</p>
      ) : (
        <div className="quest-list">
          {backups.map((backup) => (
            <article className="quest-card" key={backup.archive}>
              <div>
                <strong>{backup.archive}</strong>
                <span className="status-badge">
                  {Math.max(1, Math.round(backup.size_bytes / 1024))} KB
                </span>
              </div>
              <p>{new Date(backup.modified_at).toLocaleString("ko-KR")}</p>
              <div className="review-actions">
                <button className="quiet-button" type="button" disabled={destructiveBusy} onClick={() => onExport(backup.archive)}>
                  파일로 내보내기
                </button>
                <button className="quiet-button" type="button" disabled={destructiveBusy} onClick={() => onRestore(backup.archive)}>
                  이 백업 복원
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="activity-heading privacy-danger-zone">
        <div>
          <p className="card-label">개인정보와 삭제</p>
          <h2>아이 데이터 영구 삭제</h2>
          <p className="muted">
            선택한 아이의 현재 기록과 관련된 앱 데이터를 삭제합니다. 이미 만들어 둔 과거 백업 파일에는 해당 기록이 남아 있을 수 있으므로, 완전히 지우려면 백업 파일도 함께 삭제해 주세요.
          </p>
        </div>
      </div>
      {privacyError && <p className="form-error" role="alert">{privacyError}</p>}
      <div className="field-grid">
        <label>
          삭제할 아이
          <select
            value={deleteChildId}
            onChange={(event) => {
              setDeleteChildId(event.target.value);
              setDeleteConfirmation("");
              setPrivacyError(null);
            }}
            disabled={!connected || destructiveBusy}
          >
            <option value="">선택해 주세요</option>
            {children.map((child) => (
              <option key={child.id} value={child.id}>{child.nickname}</option>
            ))}
          </select>
        </label>
        <label>
          삭제 확인
          <input
            value={deleteConfirmation}
            onChange={(event) => setDeleteConfirmation(event.target.value)}
            placeholder={selectedDeleteChild ? `${selectedDeleteChild.nickname} 입력` : "먼저 아이를 선택해 주세요"}
            disabled={!selectedDeleteChild || destructiveBusy}
          />
        </label>
      </div>
      {selectedDeleteChild && (
        <p className="muted">실수로 삭제하지 않도록 <strong>{selectedDeleteChild.nickname}</strong>을(를) 그대로 입력해야 삭제 버튼이 활성화됩니다.</p>
      )}
      <div className="review-actions">
        <button
          className="danger-button"
          type="button"
          disabled={!connected || destructiveBusy || !deletionConfirmed}
          onClick={() => void handleDeleteChild()}
        >
          {privacyBusy ? "삭제 중…" : "아이 데이터 영구 삭제"}
        </button>
      </div>
    </section>
  );
}
