import "./WorkspaceNav.css";

export type WorkspaceView =
  | "home"
  | "record"
  | "growth"
  | "activities"
  | "materials"
  | "library"
  | "ask"
  | "settings";

const ITEMS: readonly { id: WorkspaceView; label: string; description: string }[] = [
  { id: "home", label: "홈", description: "현재 아이와 최근 상태" },
  { id: "record", label: "기록", description: "관찰과 타임라인" },
  { id: "growth", label: "성장", description: "경험 축과 성장 맥락" },
  { id: "activities", label: "활동", description: "제안과 실행 기록" },
  { id: "materials", label: "자료", description: "생성·부모 검토·인쇄" },
  { id: "library", label: "라이브러리", description: "근거 자료 관리" },
  { id: "ask", label: "질문", description: "기록 검색과 후속 질문" },
  { id: "settings", label: "설정", description: "백업과 실행 상태" },
] as const;

interface WorkspaceNavProps {
  activeView: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
}

export function WorkspaceNav({ activeView, onChange }: WorkspaceNavProps) {
  return (
    <nav className="workspace-nav" aria-label="GrowWise 작업 공간">
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`workspace-nav-item${activeView === item.id ? " active" : ""}`}
          aria-current={activeView === item.id ? "page" : undefined}
          onClick={() => onChange(item.id)}
          title={item.description}
        >
          <span>{item.label}</span>
          <small>{item.description}</small>
        </button>
      ))}
    </nav>
  );
}
