import type { FormEvent } from "react";
import { useCallback, useState } from "react";

import {
  appendConversationTurn,
  createConversation,
  searchChildContext,
  type ConversationAnswer,
  type ConversationSession,
  type SearchResponse,
} from "./api";
import { errorMessage } from "./child-context-state";

type SearchConversationOptions = {
  childId: string | null;
  getRequestId: () => number;
  scopeIsCurrent: (childId: string, requestId: number) => boolean;
};

export function useSearchConversation({
  childId,
  getRequestId,
  scopeIsCurrent,
}: SearchConversationOptions) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [conversation, setConversation] = useState<ConversationSession | null>(null);
  const [conversationAnswers, setConversationAnswers] = useState<ConversationAnswer[]>([]);
  const [conversationQuestion, setConversationQuestion] = useState("");
  const [conversationBusy, setConversationBusy] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);

  const clearSearchResult = useCallback(() => {
    setSearchResult(null);
  }, []);

  const resetSearchConversation = useCallback(() => {
    setSearchQuery("");
    setSearchResult(null);
    setSearching(false);
    setSearchError(null);
    setConversation(null);
    setConversationAnswers([]);
    setConversationQuestion("");
    setConversationBusy(false);
    setConversationError(null);
  }, []);

  function currentScope(): { childId: string; requestId: number } | null {
    if (!childId) return null;
    return { childId, requestId: getRequestId() };
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scope = currentScope();
    if (!scope) return;
    const query = searchQuery.trim();
    if (query.length < 2) {
      setSearchError("두 글자 이상으로 검색해 주세요.");
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const result = await searchChildContext(scope.childId, query);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setSearchResult(result);
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setSearchError(errorMessage(error, "검색에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setSearching(false);
    }
  }

  async function handleConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scope = currentScope();
    if (!scope) return;
    const question = conversationQuestion.trim();
    if (question.length < 2) {
      setConversationError("두 글자 이상으로 질문해 주세요.");
      return;
    }
    setConversationBusy(true);
    setConversationError(null);
    try {
      const session = conversation ?? (await createConversation(scope.childId));
      const answer = await appendConversationTurn(session.id, question);
      if (!scopeIsCurrent(scope.childId, scope.requestId)) return;
      setConversation(session);
      setConversationAnswers((current) => [...current, answer]);
      setConversationQuestion("");
    } catch (error) {
      if (scopeIsCurrent(scope.childId, scope.requestId)) {
        setConversationError(errorMessage(error, "후속 질문 처리에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(scope.childId, scope.requestId)) setConversationBusy(false);
    }
  }

  return {
    searchQuery,
    searchResult,
    searching,
    searchError,
    conversation,
    conversationAnswers,
    conversationQuestion,
    conversationBusy,
    conversationError,
    setSearchQuery,
    setConversationQuestion,
    handleSearch,
    handleConversation,
    clearSearchResult,
    resetSearchConversation,
  };
}
