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
  return (
    <nav className="workspace-nav" aria-label="GrowWise 주요 메뉴">
      <div className="workspace-nav-context">
        <span>현재 아이</span>
        <strong>{childName ?? "선택 안 됨"}</strong>
      </div>
      <div className="workspace-nav-items" role="list">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`workspace-nav-item ${active === item.id ? "active" : ""}`}
            aria-current={active === item.id ? "page" : undefined}
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
