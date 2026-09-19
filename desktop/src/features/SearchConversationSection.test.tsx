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
  it("derives a readable conversation title from the first user question", () => {
    expect(conversationSessionLabel(session)).toContain("고양이 그림");
  });

  it("renders per-answer evidence without exposing raw identifiers as primary copy", () => {
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
              source_ids: ["record:learning-log-1", "resource:resource-2"],
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

    expect(markup).toContain("AI와 대화하기");
    expect(markup).toContain("대화 목록");
    expect(markup).toContain("새 대화");
    expect(markup).toContain("연결된 원본 근거");
    expect(markup).toContain("기록 1");
    expect(markup).toContain("참고 자료 2");
    expect(markup).toContain("이전 AI 답변을 다음 답변의 근거로 재사용하지 않고 원본 기록을 다시 확인합니다");
    expect(markup).toContain("대화와 기록 백업");
    expect(markup).toContain("지금 백업");
    expect(markup).toContain("Grounding policy");
    expect(markup).toContain("기록을 직접 검색하기");
    expect(markup).not.toContain("BOUNDED MULTI-TURN");
    expect(markup).not.toContain("child scope");
  });
});
