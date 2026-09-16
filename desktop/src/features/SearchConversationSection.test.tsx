import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ConversationSession } from "../api";
import { conversationSessionLabel, SearchConversationSection } from "./SearchConversationSection";

const session: ConversationSession = {
  id: "session-12345678",
  child_id: "child-1",
  title: null,
  turns: [
    {
      role: "user",
      content: "고양이 그림에 관심 보인 기록만 다시 보여줘",
      source_ids: [],
      created_at: "2026-09-16T00:00:00Z",
    },
  ],
  created_at: "2026-09-16T00:00:00Z",
  updated_at: "2026-09-16T00:01:00Z",
};

describe("SearchConversationSection", () => {
  it("derives a readable session title from the first user question", () => {
    expect(conversationSessionLabel(session)).toContain("고양이 그림");
  });

  it("renders per-answer evidence separately from conversation context", () => {
    const markup = renderToStaticMarkup(
      <SearchConversationSection
        searchQuery=""
        searchResult={null}
        searching={false}
        searchError={null}
        conversation={session}
        conversationAnswers={[
          {
            session_id: session.id,
            thread_id: "thread-1",
            answer: {
              answer: "관련 기록을 찾았습니다.",
              source_ids: ["learning-log-1", "resource-2"],
              insufficient_evidence: false,
            },
            turn_count: 2,
          },
        ]}
        conversationQuestion=""
        conversationBusy={false}
        conversationError={null}
        onSearchQueryChange={() => undefined}
        onSearch={() => undefined}
        onConversationQuestionChange={() => undefined}
        onConversation={() => undefined}
      />,
    );

    expect(markup).toContain("현재 세션");
    expect(markup).toContain("원본 근거");
    expect(markup).toContain("learning-log-1");
    expect(markup).toContain("resource-2");
    expect(markup).toContain("대화 문장은 사실 근거로 재사용하지 않습니다");
  });
});
