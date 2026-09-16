import type { FormEvent } from "react";

import { ViewStateNotice } from "../components";
import type { ConversationAnswer, ConversationSession, SearchResponse } from "../api";
import { resultText } from "../presentation";

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
        {conversation && <p className="muted session-meta">session {conversation.id.slice(0, 8)}… · child scope 고정</p>}
        <div className="conversation-list">
          {conversationAnswers.map((item, index) => (
            <article className="conversation-card" key={`${item.session_id}-${index}`}>
              <p>{item.answer.answer}</p>
              <small>
                {item.answer.source_ids.length > 0
                  ? `근거 ${item.answer.source_ids.length}건 · ${item.answer.source_ids.join(", ")}`
                  : item.answer.insufficient_evidence
                    ? "근거 부족"
                    : "근거 없음"}
              </small>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
