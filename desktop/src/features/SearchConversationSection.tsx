import { useEffect, useMemo, useState, type FormEvent } from "react";

import { ViewStateNotice } from "../components";
import {
  listConversations,
  type BackupItem,
  type ConversationAnswer,
  type ConversationSession,
  type SearchResponse,
} from "../api";
import { resultText } from "../presentation";
import "./SearchConversationSection.css";

const LAST_CHILD_KEY = "growwise:last-child-id";

interface SearchConversationSectionProps {
  searchQuery: string;
  searchResult: SearchResponse | null;
  searching: boolean;
  searchError: string | null;
  conversation: ConversationSession | null;
  conversationAnswers: ConversationAnswer[];
  conversationQuestion: string;
  conversationBusy: boolean;
  conversationError: string | null;
  onSearchQueryChange: (value: string) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onConversationQuestionChange: (value: string) => void;
  onConversation: (event: FormEvent<HTMLFormElement>) => void;
  backups: BackupItem[];
  backupBusy: boolean;
  backupError: string | null;
  backupNotice: string | null;
  onBackupCreate: () => void;
  onBackupImport: () => void;
  onBackupExport: (archiveName: string) => void;
  onBackupRestore: (archiveName: string) => void;
}

export function conversationSessionLabel(session: ConversationSession): string {
  const explicitTitle = session.title?.trim();
  if (explicitTitle) return explicitTitle;
  const firstQuestion = session.turns.find((turn) => turn.role === "user")?.content.trim();
  if (!firstQuestion) return "새 대화";
  return firstQuestion.length > 42 ? `${firstQuestion.slice(0, 42)}…` : firstQuestion;
}

function conversationSessionTime(session: ConversationSession): string | null {
  const value = session.updated_at ?? session.created_at;
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function activeConversationChildId(conversation: ConversationSession | null): string | null {
  if (conversation) return conversation.child_id;
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(LAST_CHILD_KEY);
}

function evidenceLabel(sourceId: string, index: number): string {
  if (sourceId.startsWith("record:") || sourceId.startsWith("learning-log")) {
    return `기록 ${index + 1}`;
  }
  if (sourceId.startsWith("resource:")) return `참고 자료 ${index + 1}`;
  if (sourceId.startsWith("chunk:")) return `자료 근거 ${index + 1}`;
  return `근거 ${index + 1}`;
}

function EvidenceChips({ sourceIds }: { sourceIds: string[] }) {
  return (
    <div className="conversation-evidence">
      <strong>연결된 원본 근거</strong>
      {sourceIds.length > 0 ? (
        <>
          <div className="conversation-source-chips" aria-label={`원본 근거 ${sourceIds.length}건`}>
            {sourceIds.map((sourceId, index) => (
              <span key={sourceId} title={sourceId}>{evidenceLabel(sourceId, index)}</span>
            ))}
          </div>
          <small className="muted">답변을 만들 때 다시 확인한 저장 기록과 참고 자료입니다.</small>
        </>
      ) : (
        <span className="muted">연결된 원본 근거가 없습니다.</span>
      )}
    </div>
  );
}

export function SearchConversationSection({
  searchQuery,
  searchResult,
  searching,
  searchError,
  conversation,
  conversationAnswers,
  conversationQuestion,
  conversationBusy,
  conversationError,
  onSearchQueryChange,
  onSearch,
  onConversationQuestionChange,
  onConversation,
  backups,
  backupBusy,
  backupError,
  backupNotice,
  onBackupCreate,
  onBackupImport,
  onBackupExport,
  onBackupRestore,
}: SearchConversationSectionProps) {
  const [conversationHistory, setConversationHistory] = useState<ConversationSession[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const historyChildId = activeConversationChildId(conversation);

  useEffect(() => {
    let cancelled = false;
    if (!historyChildId) {
      setConversationHistory([]);
      setSelectedHistoryId(null);
      setHistoryError(null);
      setHistoryLoading(false);
      return () => { cancelled = true; };
    }

    setHistoryLoading(true);
    setHistoryError(null);
    void listConversations(historyChildId)
      .then((sessions) => {
        if (cancelled) return;
        setConversationHistory(sessions);
        setSelectedHistoryId((current) => {
          if (current && sessions.some((session) => session.id === current)) return current;
          if (conversation && sessions.some((session) => session.id === conversation.id)) {
            return conversation.id;
          }
          return sessions[0]?.id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setConversationHistory([]);
        setHistoryError(error instanceof Error ? error.message : "대화 기록을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });

    return () => { cancelled = true; };
  }, [conversation, conversationAnswers.length, historyChildId]);

  const selectedHistory = useMemo(
    () => conversationHistory.find((session) => session.id === selectedHistoryId) ?? null,
    [conversationHistory, selectedHistoryId],
  );
  const latestBackup = useMemo(
    () =>
      [...backups].sort(
        (left, right) => Date.parse(right.modified_at) - Date.parse(left.modified_at),
      )[0] ?? null,
    [backups],
  );

  return (
    <div className="conversation-workspace-grid">
      <div className="conversation-workspace-main">
      <section className="search-section">
        <p className="card-label">기록 검색</p>
        <h3>기억나는 말로 기록을 찾아보세요.</h3>
        <p className="muted">AI 보조 기능이 없어도 저장한 기록과 참고 자료에서 검색할 수 있습니다.</p>
        <form className="search-form" onSubmit={onSearch}>
          <input value={searchQuery} onChange={(event) => onSearchQueryChange(event.target.value)} placeholder="예: 고양이 그림에 관심 보인 기록 찾아줘" />
          <button className="primary-button" type="submit" disabled={searching}>{searching ? "검색 중…" : "검색"}</button>
        </form>
        {searchError && <p className="form-error" role="alert">{searchError}</p>}
        {searchResult && (
          <div className="search-results">
            <p className="muted">검색어: {searchResult.plan.keywords.join(", ") || searchQuery} · 결과 {searchResult.results.length}건</p>
            {searchResult.results.length === 0 ? (
              <ViewStateNotice kind="empty" title="일치하는 기록이 없습니다." description="검색어를 조금 넓히거나 다른 표현으로 다시 찾아보세요." />
            ) : (
              searchResult.results.map((result, index) => (
                <article className="search-result-card" key={String(result.id ?? index)}>
                  <p>{resultText(result)}</p>
                </article>
              ))
            )}
          </div>
        )}
      </section>

      <section className="conversation-section">
        <p className="card-label">후속 질문</p>
        <h3>찾은 맥락을 질문으로 더 좁혀보세요.</h3>
        <p className="muted">이전 답변만 믿지 않고, 질문할 때마다 저장한 원본 기록과 참고 자료를 다시 확인합니다.</p>
        <form className="search-form" onSubmit={onConversation}>
          <input value={conversationQuestion} onChange={(event) => onConversationQuestionChange(event.target.value)} placeholder="예: 그중 고양이 관련 기록만 보여줘" />
          <button className="primary-button" type="submit" disabled={conversationBusy}>
            {conversationBusy ? "확인 중…" : conversation ? "후속 질문" : "첫 질문"}
          </button>
        </form>
        {conversationError && <p className="form-error" role="alert">{conversationError}</p>}
        {conversation && <p className="muted session-meta">현재 대화를 이어서 질문할 수 있습니다.</p>}

        {conversationAnswers.length > 0 && (
          <div className="conversation-live" aria-label="현재 대화 답변">
            {conversationAnswers.map((item, index) => (
              <article className="conversation-card" key={`${item.session_id}-${index}`}>
                <p>{item.answer.answer}</p>
                <EvidenceChips sourceIds={item.answer.source_ids} />
                {item.answer.insufficient_evidence && (
                  <small className="conversation-insufficient">충분한 원본 근거를 찾지 못한 답변입니다. 기록을 직접 확인해 주세요.</small>
                )}
              </article>
            ))}
          </div>
        )}

        <div className="conversation-history-heading">
          <div>
            <p className="card-label">이전 대화</p>
            <h4>이 아이와 나눈 질문</h4>
          </div>
          <span className="muted">{conversationHistory.length}개</span>
        </div>
        <p className="conversation-evidence-policy muted">
          이전 답변 자체는 새 답변의 근거로 사용하지 않습니다. 각 답변에 표시된 원본 근거를 다시 확인합니다.
        </p>

        {historyLoading && (
          <ViewStateNotice kind="loading" title="대화 기록을 불러오는 중입니다." description="현재 아이의 저장된 대화를 확인합니다." />
        )}
        {historyError && (
          <ViewStateNotice kind="error" title="대화 기록을 불러오지 못했습니다." description={historyError} />
        )}
        {!historyLoading && !historyError && conversationHistory.length === 0 && (
          <ViewStateNotice kind="empty" title="저장된 대화가 아직 없습니다." description="첫 질문을 보내면 이 아이의 대화가 여기에 저장됩니다." />
        )}

        {conversationHistory.length > 0 && (
          <div className="conversation-history-layout">
            <div className="conversation-session-list" role="list" aria-label="저장된 대화">
              {conversationHistory.map((session) => {
                const time = conversationSessionTime(session);
                const isCurrent = conversation?.id === session.id;
                return (
                  <button
                    className={`conversation-session-button${selectedHistoryId === session.id ? " is-selected" : ""}`}
                    type="button"
                    key={session.id}
                    onClick={() => setSelectedHistoryId(session.id)}
                  >
                    <span>
                      <strong>{conversationSessionLabel(session)}</strong>
                      {isCurrent && <em>현재 대화</em>}
                    </span>
                    <small>{Math.ceil(session.turns.length / 2)}개 질문{time ? ` · ${time}` : ""}</small>
                  </button>
                );
              })}
            </div>

            {selectedHistory && (
              <div className="conversation-transcript" aria-label="선택한 대화 내용">
                <div className="conversation-transcript-heading">
                  <div>
                    <p className="card-label">대화 내용</p>
                    <h4>{conversationSessionLabel(selectedHistory)}</h4>
                  </div>
                </div>
                {selectedHistory.turns.length === 0 ? (
                  <p className="muted">아직 질문이 없는 대화입니다.</p>
                ) : (
                  selectedHistory.turns.map((turn, index) => (
                    <article className={`conversation-turn is-${turn.role}`} key={`${turn.created_at}-${index}`}>
                      <span className="conversation-turn-role">{turn.role === "user" ? "질문" : "답변"}</span>
                      <p>{turn.content}</p>
                      {turn.role === "assistant" && <EvidenceChips sourceIds={turn.source_ids} />}
                    </article>
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </section>
      </div>

      <aside className="conversation-utility-panel" aria-label="대화와 데이터 관리">
        <section className="conversation-utility-card conversation-utility-card--backup">
          <div className="conversation-utility-heading">
            <span className="conversation-utility-icon" aria-hidden="true">↺</span>
            <div>
              <p className="card-label">Backup</p>
              <h3>대화와 기록 백업</h3>
              <p>기록·사진·대화 상태를 하나의 로컬 백업으로 보관합니다.</p>
            </div>
          </div>

          <div className="conversation-backup-status">
            <span>최근 백업</span>
            <strong>
              {latestBackup
                ? new Date(latestBackup.modified_at).toLocaleString("ko-KR", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })
                : "아직 없음"}
            </strong>
            {latestBackup && (
              <small>{Math.max(1, Math.round(latestBackup.size_bytes / 1024))} KB</small>
            )}
          </div>

          {backupError && <p className="form-error" role="alert">{backupError}</p>}
          {backupNotice && <p className="conversation-backup-notice" role="status">{backupNotice}</p>}

          <div className="conversation-backup-actions">
            <button type="button" className="primary-button" disabled={backupBusy} onClick={onBackupCreate}>
              {backupBusy ? "처리 중…" : "지금 백업"}
            </button>
            <button type="button" className="quiet-button" disabled={backupBusy} onClick={onBackupImport}>
              백업 가져오기
            </button>
          </div>

          {latestBackup && (
            <div className="conversation-backup-secondary">
              <button
                type="button"
                disabled={backupBusy}
                onClick={() => onBackupExport(latestBackup.archive)}
              >
                파일로 내보내기
              </button>
              <button
                type="button"
                disabled={backupBusy}
                onClick={() => onBackupRestore(latestBackup.archive)}
              >
                이 백업 복원
              </button>
            </div>
          )}
        </section>

        <section className="conversation-utility-card">
          <p className="card-label">Grounding policy</p>
          <h3>답변은 저장된 원본을 다시 확인합니다.</h3>
          <p>
            이전 AI 답변을 다음 답변의 근거로 재사용하지 않고, 기록과 참고 자료에서 매번 다시 찾습니다.
          </p>
          <div className="conversation-policy-badges">
            <span>Local-first</span>
            <span>근거 표시</span>
            <span>부족한 근거 경고</span>
          </div>
        </section>
      </aside>
    </div>
  );
}
