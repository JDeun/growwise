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
  backups?: BackupItem[];
  backupBusy?: boolean;
  backupError?: string | null;
  backupNotice?: string | null;
  onCreateBackup?: () => void;
  onImportBackup?: () => void;
  onExportBackup?: (archiveName: string) => void;
  onRestoreBackup?: (archiveName: string) => void;
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
          <small>새 답변마다 저장된 원본을 다시 확인합니다.</small>
        </>
      ) : (
        <span className="muted">연결된 원본 근거가 없습니다.</span>
      )}
    </div>
  );
}

function BackupUtility({
  backups,
  busy,
  error,
  notice,
  onCreate,
  onImport,
  onExport,
  onRestore,
}: {
  backups: BackupItem[];
  busy: boolean;
  error: string | null;
  notice: string | null;
  onCreate?: () => void;
  onImport?: () => void;
  onExport?: (archiveName: string) => void;
  onRestore?: (archiveName: string) => void;
}) {
  const ordered = [...backups].sort(
    (left, right) => Date.parse(right.modified_at) - Date.parse(left.modified_at),
  );
  const latest = ordered[0];

  return (
    <section className="conversation-backup-card" aria-labelledby="conversation-backup-title">
      <div className="conversation-utility-heading">
        <div>
          <p className="card-label">Backup</p>
          <h4 id="conversation-backup-title">백업 및 복원</h4>
        </div>
        <span className={latest ? "backup-health is-ready" : "backup-health"}>
          {latest ? "Ready" : "Empty"}
        </span>
      </div>
      {latest ? (
        <div className="backup-latest">
          <span>최근 백업</span>
          <strong>{latest.archive}</strong>
          <small>{new Date(latest.modified_at).toLocaleString("ko-KR")}</small>
        </div>
      ) : (
        <p className="conversation-utility-empty">아직 만든 백업이 없습니다.</p>
      )}
      <div className="backup-utility-actions">
        <button type="button" className="primary-button" onClick={onCreate} disabled={busy || !onCreate}>
          {busy ? "처리 중…" : "지금 백업"}
        </button>
        <button type="button" className="quiet-button" onClick={onImport} disabled={busy || !onImport}>
          가져오기
        </button>
      </div>
      {latest && (onExport || onRestore) ? (
        <div className="backup-latest-actions">
          {onExport ? (
            <button type="button" onClick={() => onExport(latest.archive)} disabled={busy}>
              내보내기
            </button>
          ) : null}
          {onRestore ? (
            <button type="button" onClick={() => onRestore(latest.archive)} disabled={busy}>
              이 백업 복원
            </button>
          ) : null}
        </div>
      ) : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {notice ? <p className="backup-notice" role="status">{notice}</p> : null}
    </section>
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
  backups = [],
  backupBusy = false,
  backupError = null,
  backupNotice = null,
  onCreateBackup,
  onImportBackup,
  onExportBackup,
  onRestoreBackup,
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
      return () => {
        cancelled = true;
      };
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

    return () => {
      cancelled = true;
    };
  }, [conversation, conversationAnswers.length, historyChildId]);

  const selectedHistory = useMemo(
    () => conversationHistory.find((session) => session.id === selectedHistoryId) ?? null,
    [conversationHistory, selectedHistoryId],
  );
  const displayedSession = selectedHistory ?? conversation;
  const latestAnswer = conversationAnswers.at(-1);

  return (
    <section className="conversation-section conversation-studio" aria-label="대화와 검색 작업공간">
      <aside className="conversation-studio-sidebar">
        <div className="conversation-sidebar-heading">
          <div>
            <p className="card-label">History</p>
            <h3>대화 기록</h3>
          </div>
          <span>{conversationHistory.length}</span>
        </div>
        {historyLoading ? (
          <ViewStateNotice kind="loading" title="대화 기록을 불러오는 중입니다." description="현재 아이의 저장된 대화를 확인합니다." />
        ) : null}
        {historyError ? (
          <ViewStateNotice kind="error" title="대화 기록을 불러오지 못했습니다." description={historyError} />
        ) : null}
        {!historyLoading && !historyError && conversationHistory.length === 0 ? (
          <div className="conversation-sidebar-empty">
            <span aria-hidden="true">＋</span>
            <strong>첫 대화를 시작해 보세요.</strong>
            <small>질문과 답변은 아이별로 저장됩니다.</small>
          </div>
        ) : null}
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
                  {isCurrent ? <em>현재</em> : null}
                </span>
                <small>{Math.ceil(session.turns.length / 2)}개 질문{time ? ` · ${time}` : ""}</small>
              </button>
            );
          })}
        </div>
        <div className="conversation-history-policy">
          <span aria-hidden="true">⌁</span>
          <p>이전 답변은 새 질문의 근거로 재사용하지 않습니다.</p>
        </div>
      </aside>

      <section className="conversation-chat-stage">
        <header className="conversation-chat-header">
          <div>
            <p className="card-label">GrowWise Assistant</p>
            <h3>{displayedSession ? conversationSessionLabel(displayedSession) : "새 대화"}</h3>
          </div>
          <span className="conversation-grounded-chip">Grounded</span>
        </header>

        <div className="conversation-transcript conversation-chat-scroll" aria-label="선택한 대화 내용">
          {!displayedSession && conversationAnswers.length === 0 ? (
            <div className="conversation-welcome">
              <span aria-hidden="true">G</span>
              <h3>아이의 기록에 대해 물어보세요.</h3>
              <p>GrowWise는 저장된 관찰·학습 기록과 참고 자료를 다시 확인한 뒤 답합니다.</p>
            </div>
          ) : null}

          {displayedSession?.turns.map((turn, index) => (
            <article className={`conversation-turn is-${turn.role}`} key={`${turn.created_at}-${index}`}>
              <span className="conversation-turn-role">{turn.role === "user" ? "나" : "GrowWise"}</span>
              <p>{turn.content}</p>
              {turn.role === "assistant" ? <EvidenceChips sourceIds={turn.source_ids} /> : null}
            </article>
          ))}

          {conversationAnswers.map((item, index) => (
            <article className="conversation-turn is-assistant is-live" key={`${item.session_id}-live-${index}`}>
              <span className="conversation-turn-role">GrowWise · 지금 답변</span>
              <p>{item.answer.answer}</p>
              <EvidenceChips sourceIds={item.answer.source_ids} />
              {item.answer.insufficient_evidence ? (
                <small className="conversation-insufficient">
                  충분한 원본 근거를 찾지 못했습니다. 기록을 직접 확인해 주세요.
                </small>
              ) : null}
            </article>
          ))}
        </div>

        <form className="conversation-composer" onSubmit={onConversation}>
          <div className="conversation-composer-input">
            <input
              value={conversationQuestion}
              onChange={(event) => onConversationQuestionChange(event.target.value)}
              placeholder="아이의 기록에 대해 질문해 보세요…"
              maxLength={2000}
            />
            <span>원본 기록 기반</span>
          </div>
          <button className="primary-button" type="submit" disabled={conversationBusy}>
            {conversationBusy ? "확인 중…" : conversation ? "보내기" : "대화 시작"}
          </button>
        </form>
        {conversationError ? <p className="form-error conversation-chat-error" role="alert">{conversationError}</p> : null}
      </section>

      <aside className="conversation-utility-panel">
        <section className="search-section conversation-search-card">
          <div className="conversation-utility-heading">
            <div>
              <p className="card-label">Search</p>
              <h4>기록 검색</h4>
            </div>
            <span className="utility-count">{searchResult?.results.length ?? 0}</span>
          </div>
          <form className="conversation-utility-search" onSubmit={onSearch}>
            <input
              value={searchQuery}
              onChange={(event) => onSearchQueryChange(event.target.value)}
              placeholder="기억나는 말로 검색"
              maxLength={2000}
            />
            <button type="submit" disabled={searching} aria-label="검색">
              {searching ? "…" : "↗"}
            </button>
          </form>
          {searchError ? <p className="form-error" role="alert">{searchError}</p> : null}
          {searchResult ? (
            <div className="conversation-search-results">
              {searchResult.results.length === 0 ? (
                <p>일치하는 기록이 없습니다.</p>
              ) : (
                searchResult.results.slice(0, 4).map((result, index) => (
                  <article key={String(result.id ?? index)}>
                    <span>{index + 1}</span>
                    <p>{resultText(result)}</p>
                  </article>
                ))
              )}
            </div>
          ) : (
            <p className="conversation-utility-empty">관찰·학습·참고 자료를 빠르게 찾습니다.</p>
          )}
        </section>

        <section className="conversation-source-card">
          <div className="conversation-utility-heading">
            <div>
              <p className="card-label">Evidence</p>
              <h4>현재 답변 근거</h4>
            </div>
          </div>
          {latestAnswer ? (
            <EvidenceChips sourceIds={latestAnswer.answer.source_ids} />
          ) : (
            <p className="conversation-utility-empty">답변이 생성되면 사용한 원본 근거가 표시됩니다.</p>
          )}
        </section>

        <BackupUtility
          backups={backups}
          busy={backupBusy}
          error={backupError}
          notice={backupNotice}
          onCreate={onCreateBackup}
          onImport={onImportBackup}
          onExport={onExportBackup}
          onRestore={onRestoreBackup}
        />
      </aside>
    </section>
  );
}
