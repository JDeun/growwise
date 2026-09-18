import "./WorkspaceNav.css";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceNavProps = {
  activeView: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
};

const PRIMARY_VIEWS: readonly WorkspaceView[] = [
  "home",
  "profile",
  "learning",
  "materials",
  "photos",
  "search",
  "settings",
];

const SECONDARY_VIEWS: readonly WorkspaceView[] = [
  "observations",
  "growth",
  "activities",
  "discovery",
  "library",
];

function NavIcon({ view }: { view: WorkspaceView }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (view === "home") return <svg {...common}><path d="M3.5 10.5 12 3l8.5 7.5"/><path d="M5.5 9.5V21h13V9.5"/><path d="M9.5 21v-6h5v6"/></svg>;
  if (view === "profile") return <svg {...common}><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-4 3.2-6 7-6s6.2 2 7 6"/></svg>;
  if (view === "learning" || view === "observations") return <svg {...common}><path d="M5 4.5h11.5A2.5 2.5 0 0 1 19 7v13H7.5A2.5 2.5 0 0 1 5 17.5z"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/></svg>;
  if (view === "materials" || view === "library" || view === "discovery") return <svg {...common}><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 5.5v16"/></svg>;
  if (view === "photos") return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 15-4.5-4.5L8 19"/></svg>;
  if (view === "search") return <svg {...common}><path d="M7 18.5 3.5 21l1.2-4.2A8 8 0 1 1 7 18.5Z"/><path d="M8.5 10.5h7M8.5 14h4.5"/></svg>;
  if (view === "settings") return <svg {...common}><path d="M5 5h14v16H5z"/><path d="M8 3v4M16 3v4M8 11h8M8 15h5"/></svg>;
  if (view === "growth") return <svg {...common}><path d="M4 19V9M10 19V5M16 19v-8M22 19H2"/></svg>;
  if (view === "activities") return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="m9 12 2 2 4-5"/></svg>;
  return <svg {...common}><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>;
}

function NavItem({
  view,
  activeView,
  onChange,
}: {
  view: WorkspaceView;
  activeView: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
}) {
  const active = view === activeView;
  return (
    <button
      id={`workspace-nav-${view}`}
      type="button"
      className={`workspace-nav-item ${active ? "active" : ""}`}
      aria-current={active ? "page" : undefined}
      aria-controls="workspace-panel"
      onClick={() => onChange(view)}
    >
      <NavIcon view={view} />
      <span>{WORKSPACE_LABELS[view]}</span>
    </button>
  );
}

export function WorkspaceNav({ activeView, onChange }: WorkspaceNavProps) {
  return (
    <nav className="workspace-nav" aria-label="GrowWise 주요 메뉴">
      <button className="workspace-brand" type="button" onClick={() => onChange("home")} aria-label="GrowWise 대시보드로 이동">
        <span className="workspace-brand-mark" aria-hidden="true">
          <img src="/growwise-symbol.svg" alt="" />
        </span>
        <strong>GrowWise</strong>
      </button>

      <div className="workspace-nav-primary">
        {PRIMARY_VIEWS.map((view) => (
          <NavItem key={view} view={view} activeView={activeView} onChange={onChange} />
        ))}
      </div>

      <div className="workspace-nav-secondary">
        <p>추가 도구</p>
        {SECONDARY_VIEWS.map((view) => (
          <NavItem key={view} view={view} activeView={activeView} onChange={onChange} />
        ))}
      </div>

      <div className="workspace-nav-footer">
        <span className="workspace-local-dot" aria-hidden="true" />
        <span><strong>Local-first</strong><small>기록은 이 기기에 저장됩니다.</small></span>
      </div>
    </nav>
  );
}
