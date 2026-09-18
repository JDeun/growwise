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
  "conversation",
  "backup",
];

const UTILITY_VIEWS: readonly WorkspaceView[] = ["settings", "help"];

function NavIcon({ view }: { view: WorkspaceView }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (view === "home") return <svg {...common}><path d="M3.5 10.5 12 3l8.5 7.5"/><path d="M5.5 9.5V21h13V9.5"/><path d="M9.5 21v-6h5v6"/></svg>;
  if (view === "profile") return <svg {...common}><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-4 3.2-6 7-6s6.2 2 7 6"/></svg>;
  if (view === "learning") return <svg {...common}><path d="M5 4.5h11.5A2.5 2.5 0 0 1 19 7v13H7.5A2.5 2.5 0 0 1 5 17.5z"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/></svg>;
  if (view === "materials") return <svg {...common}><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 5.5v16"/></svg>;
  if (view === "photos") return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 15-4.5-4.5L8 19"/></svg>;
  if (view === "conversation") return <svg {...common}><path d="M7 18.5 3.5 21l1.2-4.2A8 8 0 1 1 7 18.5Z"/><path d="M8.5 10.5h7M8.5 14h4.5"/></svg>;
  if (view === "backup") return <svg {...common}><path d="M5 5h14v16H5z"/><path d="M8 3v4M16 3v4M8 11h8M8 15h5"/></svg>;
  if (view === "settings") return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.86 2.86-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21H9.6v-.1A1.7 1.7 0 0 0 8.2 19.3a1.7 1.7 0 0 0-1.08.44l-.06.06-2.86-2.86.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.6-1H3V10h.1A1.7 1.7 0 0 0 4.7 8.6a1.7 1.7 0 0 0-.44-1.08l-.06-.06L7.06 4.6l.06.06A1.7 1.7 0 0 0 9 5a1.7 1.7 0 0 0 1-1.6V3h4v.1A1.7 1.7 0 0 0 15.4 4.7a1.7 1.7 0 0 0 1.08-.44l.06-.06 2.86 2.86-.06.06A1.7 1.7 0 0 0 19 9a1.7 1.7 0 0 0 1.6 1h.4v4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg>;
  if (view === "help") return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.4 2.4 0 1 1 3.7 2c-.9.6-1.5 1.1-1.5 2.2"/><path d="M12 17h.01"/></svg>;

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
      <span className="workspace-nav-icon"><NavIcon view={view} /></span>
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

      <div className="workspace-nav-utility" aria-label="앱 메뉴">
        {UTILITY_VIEWS.map((view) => (
          <NavItem key={view} view={view} activeView={activeView} onChange={onChange} />
        ))}
      </div>
    </nav>
  );
}
