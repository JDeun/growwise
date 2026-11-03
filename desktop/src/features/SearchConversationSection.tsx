import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { ConfirmDialog, ViewStateNotice } from "../components";
import { deleteConversation } from "../record-actions-api";
import { useOptionalActiveChild, readRememberedChildId } from "../active-child-context";
import {
  listConversations,
  type BackupItem,
  type ConversationAnswer,
  type ConversationSession,
  type SearchResponse,
  type MaterialAction,
} from "../api";
import { resultText } from "../presentation";
import { ConversationEvidence as EvidenceChips } from "./ConversationEvidence";
import "./SearchConversationSection.css";

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
  onCreateMaterial?: (action: MaterialAction) => void;
  onNewConversation?: () => void;
  onSelectConversation?: (session: ConversationSession) => void;
  backups?: BackupItem[];
  backupBusy?: boolean;
  backupError?: string | null;
  backupNotice?: string | null;
  onBackupCreate?: () => void;
  onBackupImport?: () => void;
  onBackupExport?: (archiveName: string) => void;
  onBackupRestore?: (archiveName: string) => void;
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
  return readRememberedChildId(window.localStorage);
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
  onCreateMaterial,
  onNewConversation = () => undefined,
  onSelectConversation = () => undefined,
  backups = [],
  backupBusy = false,
  backupError = null,
  backupNotice = null,
  onBackupCreate = () => undefined,
  onBackupImport = () => undefined,
  onBackupExport = () => undefined,
  onBackupRestore = () => undefined,
}: SearchConversationSectionProps) {
  const [conversationHistory, setConversationHistory] = useState<ConversationSession[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [newConversationMode, setNewConversationMode] = useState(false);
  const sharedChild = useOptionalActiveChild();
  const historyChildId = sharedChild?.activeChildId ?? activeConversationChildId(conversation);
  const visibleHistory = conversationHistory.filter((session) => session.child_id === historyChildId);
  const currentChildId = useRef(historyChildId);
  currentChildId.current = historyChildId;
  const [deleteTarget, setDeleteTarget] = useState<ConversationSession | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setDeleteTarget(null);
    setDeleting(false);
  }, [historyChildId]);

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
          if (newConversationMode) return null;
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
  }, [conversation, conversationAnswers.length, historyChildId, newConversationMode]);

  useEffect(() => {
    if (!conversation) return;
    setNewConversationMode(false);
    setSelectedHistoryId(conversation.id);
  }, [conversation]);

  function handleNewConversation() {
    setNewConversationMode(true);
    setSelectedHistoryId(null);
    onNewConversation();
  }

  const selectedHistory = useMemo(
    () => conversationHistory.find((session) =>
      session.id === selectedHistoryId && session.child_id === historyChildId,
    ) ?? null,
    [conversationHistory, selectedHistoryId, historyChildId],
  );
  const activeConversation = conversation?.child_id === historyChildId ? conversation : null;
  const deletableSession = activeConversation ?? selectedHistory;

  async function handleDelete() {
    if (!deleteTarget || deleting || conversationBusy) return;
    const childId = historyChildId;
    setDeleting(true);
    setHistoryError(null);
    try {
      await deleteConversation(deleteTarget.id);
      if (currentChildId.current !== childId) return;
      setConversationHistory((sessions) => sessions.filter((session) => session.id !== deleteTarget.id));
      setDeleteTarget(null);
      handleNewConversation();
    } catch (cause) {
      if (currentChildId.current === childId) {
        setHistoryError(cause instanceof Error ? cause.message : String(cause));
        setDeleteTarget(null);
      }
    } finally {
      if (currentChildId.current === childId) setDeleting(false);
    }
  }
  const latestBackup = useMemo(
    () =>
      [...backups].sort(
        (left, right) => Date.parse(right.modified_at) - Date.parse(left.modified_at),
      )[0] ?? null,
    [backups],
  );

  return (
    <section className="conversation-workspace-grid" aria-labelledby="conversation-workspace-title">
      <header className="conversation-product-heading">
        <div>
          <h2 id="conversation-workspace-title">AI와 대화하기</h2>
          <p>아이의 기록과 저장한 참고 자료를 다시 확인해 근거가 연결된 답변을 만듭니다.</p>
        </div>
      </header>

      <aside className="conversation-history-pane" aria-label="대화 목록">
        <div className="conversation-pane-heading">
          <div>
            <h3>이전 대화</h3>
          </div>
          <span>{visibleHistory.length}</span>
        </div>

        <button
          type="button"
          className="conversation-new-button"
          onClick={handleNewConversation}
          disabled={conversationBusy}
        >
          <span aria-hidden="true">＋</span>
          새 대화
        </button>

        {deletableSession && (
          <button type="button" className="quiet-button" disabled={conversationBusy || deleting}
            onClick={() => setDeleteTarget(deletableSession)}>
            선택한 대화 삭제
          </button>
        )}

        {historyLoading && (
          <ViewStateNotice kind="loading" title="대화 기록을 불러오는 중입니다." description="현재 아이의 저장된 대화를 확인합니다." />
        )}
        {historyError && (
          <ViewStateNotice kind="error" title="대화 기록을 불러오지 못했습니다." description={historyError} />
        )}
        {!historyLoading && !historyError && visibleHistory.length === 0 && (
          <ViewStateNotice kind="empty" title="저장된 대화가 없습니다." description="중앙 입력창에서 첫 질문을 보내면 대화가 저장됩니다." />
        )}

        {visibleHistory.length > 0 && (
          <div className="conversation-session-list" role="list" aria-label="저장된 대화">
            {visibleHistory.map((session) => {
              const time = conversationSessionTime(session);
              const isCurrent = conversation?.id === session.id;
              return (
                <button
                  className={`conversation-session-button${selectedHistoryId === session.id ? " is-selected" : ""}`}
                  type="button"
                  disabled={conversationBusy || deleting}
                  key={session.id}
                  onClick={() => {
                    setNewConversationMode(false);
                    setSelectedHistoryId(session.id);
                    onSelectConversation(session);
                  }}
                >
                  <span>
                    <strong>{conversationSessionLabel(session)}</strong>
                    {isCurrent && <em>현재</em>}
                  </span>
                  <small>{Math.ceil(session.turns.length / 2)}개 질문{time ? ` · ${time}` : ""}</small>
                </button>
              );
            })}
          </div>
        )}

        <p className="conversation-evidence-policy muted">
          이전 AI 답변을 다음 답변의 근거로 재사용하지 않고 원본 기록을 다시 확인합니다.
        </p>
      </aside>

      <section className="conversation-chat-pane" aria-label="대화 내용">
        <div className="conversation-pane-heading conversation-chat-heading">
          <div>
            <h3>{selectedHistory ? conversationSessionLabel(selectedHistory) : "무엇이든 물어보세요"}</h3>
          </div>
          {selectedHistory && <span>{Math.ceil(selectedHistory.turns.length / 2)}개 질문</span>}
        </div>

        <div className="conversation-chat-scroll">
          {selectedHistory?.turns.length ? (
            selectedHistory.turns.map((turn, index) => (
              <article className={`conversation-turn is-${turn.role}`} key={`${turn.created_at}-${index}`}>
                <span className="conversation-turn-role">{turn.role === "user" ? "나" : "GrowWise"}</span>
                <p>{turn.content}</p>
                {turn.role === "assistant" && <EvidenceChips childId={historyChildId} sourceIds={turn.source_ids} />}
                {turn.material_action && onCreateMaterial && (
                  <button type="button" className="quiet-button" onClick={() => onCreateMaterial(turn.material_action!)}>
                    이 내용으로 활동 만들기
                  </button>
                )}
              </article>
            ))
          ) : (
            <div className="conversation-chat-empty">
              <span aria-hidden="true">✦</span>
              <strong>아이의 기록을 바탕으로 대화를 시작해 보세요.</strong>
              <p>예: 최근 공룡에 관심을 보인 기록을 정리해줘.</p>
            </div>
          )}

          {activeConversation && conversationAnswers.length > 0 && selectedHistory?.id !== activeConversation.id && (
            <div className="conversation-live" aria-label="현재 대화 답변">
              {conversationAnswers.map((item, index) => (
                <article className="conversation-turn is-assistant" key={`${item.session_id}-${index}`}>
                  <span className="conversation-turn-role">GrowWise</span>
                  <p>{item.answer.answer}</p>
                  <EvidenceChips childId={historyChildId} sourceIds={item.answer.source_ids} />
                  {item.answer.material_action && onCreateMaterial && (
                    <button type="button" className="quiet-button" onClick={() => onCreateMaterial(item.answer.material_action!)}>
                      이 내용으로 활동 만들기
                    </button>
                  )}
                  {item.answer.insufficient_evidence && (
                    <small className="conversation-insufficient">충분한 원본 근거를 찾지 못했습니다. 기록을 직접 확인해 주세요.</small>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>

        {conversationError && <p className="form-error conversation-chat-error" role="alert">{conversationError}</p>}
        <form className="conversation-composer" onSubmit={onConversation}>
          <input
            value={conversationQuestion}
            onChange={(event) => onConversationQuestionChange(event.target.value)}
            placeholder="아이의 기록에 대해 질문해 보세요..."
          />
          <button className="primary-button" type="submit" disabled={conversationBusy || !conversationQuestion.trim()}>
            <span aria-hidden="true">↑</span>
            <span className="sr-only">{conversationBusy ? "확인 중" : "질문 보내기"}</span>
          </button>
        </form>

        <details className="conversation-search-tools">
          <summary>기록을 직접 검색하기</summary>
          <form className="search-form" onSubmit={onSearch}>
            <input
              value={searchQuery}
              onChange={(event) => onSearchQueryChange(event.target.value)}
              placeholder="예: 고양이 그림에 관심 보인 기록 찾아줘"
            />
            <button className="quiet-button" type="submit" disabled={searching}>{searching ? "검색 중…" : "검색"}</button>
          </form>
          {searchError && <p className="form-error" role="alert">{searchError}</p>}
          {searchResult && (
            <div className="search-results">
              <p className="muted">검색 결과 {searchResult.results.length}건</p>
              {searchResult.results.length === 0 ? (
                <ViewStateNotice kind="empty" title="일치하는 기록이 없습니다." description="검색어나 표현을 바꿔 다시 찾아보세요." />
              ) : (
                searchResult.results.map((result, index) => (
                  <article className="search-result-card" key={String(result.id ?? index)}>
                    <p>{resultText(result)}</p>
                  </article>
                ))
              )}
            </div>
          )}
        </details>
      </section>

      <aside className="conversation-utility-panel" aria-label="대화와 데이터 관리">
        <section className="conversation-utility-card conversation-utility-card--backup">
          <div className="conversation-utility-heading">
            <span className="conversation-utility-icon" aria-hidden="true">↺</span>
            <div>
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
            {latestBackup && <small>{Math.max(1, Math.round(latestBackup.size_bytes / 1024))} KB</small>}
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
              <button type="button" disabled={backupBusy} onClick={() => onBackupExport(latestBackup.archive)}>
                파일로 내보내기
              </button>
              <button type="button" disabled={backupBusy} onClick={() => onBackupRestore(latestBackup.archive)}>
                이 백업 복원
              </button>
            </div>
          )}
        </section>

        <section className="conversation-utility-card">
          <h3>답변은 저장된 원본을 다시 확인합니다.</h3>
          <p>이전 AI 답변 대신 기록과 참고 자료를 매번 다시 찾아 근거를 표시합니다.</p>
          <div className="conversation-policy-badges">
            <span>Local-first</span>
            <span>근거 표시</span>
            <span>부족한 근거 경고</span>
          </div>
        </section>
      </aside>
      <ConfirmDialog open={deleteTarget !== null} title="선택한 대화를 삭제할까요?"
        description="이 대화의 질문과 답변을 삭제합니다. 아이의 원본 기록과 참고 자료는 보존됩니다."
        confirmLabel="대화 삭제" destructive busy={deleting}
        onCancel={() => setDeleteTarget(null)} onConfirm={() => void handleDelete()} />
    </section>
  );
}
