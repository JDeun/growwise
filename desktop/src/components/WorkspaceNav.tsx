import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { isRovingKey, nextWorkspaceIndex } from "../a11y";

export type WorkspaceView =
  | "home"
  | "record"
  | "growth"
  | "activities"
  | "materials"
  | "library"
  | "ask"
  | "settings";

const ITEMS: Array<{ id: WorkspaceView; label: string; description: string }> = [
  { id: "home", label: "홈", description: "최근 기록과 다음 할 일" },
  { id: "record", label: "기록", description: "관찰과 타임라인" },
  { id: "growth", label: "성장", description: "경험 축과 성장 맥락" },
  { id: "activities", label: "활동", description: "활동 제안과 진행 상태" },
  { id: "materials", label: "학습자료", description: "생성·부모 검토·인쇄" },
  { id: "library", label: "자료실", description: "Resource KB 관리" },
  { id: "ask", label: "질문", description: "기록 검색과 후속 질문" },
  { id: "settings", label: "설정", description: "백업과 실행 환경" },
];

interface WorkspaceNavProps {
  active: WorkspaceView;
  childName?: string;
  onChange: (view: WorkspaceView) => void;
}

export function WorkspaceNav({ active, childName, onChange }: WorkspaceNavProps) {
  const activeIndex = Math.max(
    0,
    ITEMS.findIndex((item) => item.id === active),
  );
  // Roving tabindex: exactly one item is in the tab order at a time, and the
  // arrow keys move focus between items (WAI-ARIA toolbar pattern).
  const [focusIndex, setFocusIndex] = useState(activeIndex);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    // Keep the tab stop on the current page when it changes elsewhere.
    setFocusIndex(activeIndex);
  }, [activeIndex]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!isRovingKey(event.key)) return;
    event.preventDefault();
    const target = nextWorkspaceIndex(focusIndex, event.key, ITEMS.length);
    setFocusIndex(target);
    itemRefs.current[target]?.focus();
  }

  return (
    <nav className="workspace-nav" aria-label="GrowWise 주요 메뉴">
      <div className="workspace-nav-context">
        <span>현재 아이</span>
        <strong>{childName ?? "선택 안 됨"}</strong>
      </div>
      <div className="workspace-nav-items" role="toolbar" aria-orientation="vertical">
        {ITEMS.map((item, index) => (
          <button
            key={item.id}
            ref={(element) => {
              itemRefs.current[index] = element;
            }}
            type="button"
            className={`workspace-nav-item ${active === item.id ? "active" : ""}`}
            aria-current={active === item.id ? "page" : undefined}
            tabIndex={index === focusIndex ? 0 : -1}
            onKeyDown={handleKeyDown}
            onClick={() => onChange(item.id)}
          >
            <span>{item.label}</span>
            <small>{item.description}</small>
          </button>
        ))}
      </div>
    </nav>
  );
}
