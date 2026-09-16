import { useEffect, useMemo, useState, type FormEvent } from "react";

import { ViewStateNotice } from "../components";
import {
  listConversations,
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

function EvidenceChips({ sourceIds }: { sourceIds: string[] }) {
  return (
    <div className="conversation-evidence">
      <strong>원본 근거</strong>
      {sourceIds.length > 0 ? (
        <div className="conversation-source-chips" aria-label="답변 원본 근거 ID">
          {sourceIds.map((sourceId) => <span key={sourceId}>{sourceId}</span>)}
        </div>
      ) : (
        <span className="muted">연결된 원본 근거 ID가 없습니다.</span>
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

  return (
    <>
      <section className="search-section">
        <p className="card-label">NATURAL-LANGUAGE SEARCH</p>
        <h3>기록을 자연어로 찾습니다.</h3>
        <p className="muted">AI가 없어도 child-scoped lexical 검색이 작동합니다.</p>
        <form className="search-form" onSubmit={onSearch}>
          <input value={searchQuery} onChange={(event) => onSearchQueryChange(event.target.value)} placeholder="예: 고양이 그림에 관심 보인 기록 찾아줘" />
          <button className="primary-button" type="submit" disabled={searching}>{searching ? "검색 중…" : "검색"}</button>
        </form>
        {searchError && <p className="form-error" role="alert">{searchError}</p>}
        {searchResult && (
          <div className="search-results">
            <p className="muted">검색 키워드: {searchResult.plan.keywords.join(", ") || "원문 사용"} · 결과 {searchResult.results.length}건</p>
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
        <p className="card-label">BOUNDED MULTI-TURN</p>
        <h3>후속 질문으로 맥락을 좁힙니다.</h3>
        <p className="muted">대화는 지시어 해석에만 쓰고, 사실 근거는 매 턴 원본 기록과 Resource KB에서 다시 찾습니다.</p>
        <form className="search-form" onSubmit={onConversation}>
          <input value={conversationQuestion} onChange={(event) => onConversationQuestionChange(event.target.value)} placeholder="예: 그중 고양이 관련 기록만 보여줘" />
          <button className="primary-button" type="submit" disabled={conversationBusy}>
            {conversationBusy ? "확인 중…" : conversation ? "후속 질문" : "세션 시작"}
          </button>
        </form>
        {conversationError && <p className="form-error" role="alert">{conversationError}</p>}
        {conversation && <p className="muted session-meta">현재 세션 {conversation.id.slice(0, 8)}… · child scope 고정</p>}

        {conversationAnswers.length > 0 && (
          <div className="conversation-live" aria-label="현재 세션 답변">
            {conversationAnswers.map((item, index) => (
              <article className="conversation-card" key={`${item.session_id}-${index}`}>
                <p>{item.answer.answer}</p>
                <EvidenceChips sourceIds={item.answer.source_ids} />
                {item.answer.insufficient_evidence && (
                  <small className="conversation-insufficient">이 답변은 충분한 원본 근거를 찾지 못했습니다.</small>
                )}
              </article>
            ))}
          </div>
        )}

        <div className="conversation-history-heading">
          <div>
            <p className="card-label">SESSION HISTORY</p>
            <h4>이 아이의 이전 대화</h4>
          </div>
          <span className="muted">{conversationHistory.length}개 세션</span>
        </div>
        <p className="conversation-evidence-policy muted">
          대화 문장은 사실 근거로 재사용하지 않습니다. 각 assistant 답변 아래의 원본 근거 ID는 그 턴에서 다시 조회한 기록·Resource KB를 가리킵니다.
        </p>

        {historyLoading && (
          <ViewStateNotice kind="loading" title="대화 기록을 불러오는 중입니다." description="현재 아이 범위의 저장된 세션을 확인합니다." />
        )}
        {historyError && (
          <ViewStateNotice kind="error" title="대화 기록을 불러오지 못했습니다." description={historyError} />
        )}
        {!historyLoading && !historyError && conversationHistory.length === 0 && (
          <ViewStateNotice kind="empty" title="저장된 대화가 아직 없습니다." description="첫 질문을 보내면 child scope가 고정된 세션이 여기에 저장됩니다." />
        )}

        {conversationHistory.length > 0 && (
          <div className="conversation-history-layout">
            <div className="conversation-session-list" role="list" aria-label="저장된 대화 세션">
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
                      {isCurrent && <em>현재 세션</em>}
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
                    <p className="card-label">SESSION DETAIL</p>
                    <h4>{conversationSessionLabel(selectedHistory)}</h4>
                  </div>
                  <span className="muted">{selectedHistory.id.slice(0, 8)}…</span>
                </div>
                {selectedHistory.turns.length === 0 ? (
                  <p className="muted">아직 질문이 없는 세션입니다.</p>
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
    </>
  );
}
