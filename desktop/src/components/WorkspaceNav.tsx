import { useActiveChild } from "../active-child-context";
import { ChildAvatar } from "./ChildAvatar";
import "./WorkspaceNav.css";
import { WORKSPACE_DESCRIPTIONS } from "./workspaceDescriptions";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import type { WorkspaceView } from "./workspaceTypes";

type WorkspaceNavProps = {
  activeView: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
};

type WorkspaceGroup = {
  key: string;
  label?: string;
  views: readonly WorkspaceView[];
  utility?: boolean;
};

const WORKSPACE_GROUPS: readonly WorkspaceGroup[] = [
  { key: "overview", views: ["home"] },
  {
    key: "records",
    label: "아이와 기록",
    views: ["observations", "photos", "learning", "growth", "activities"],
  },
  {
    key: "resources",
    label: "지식과 자료",
    views: ["search", "discovery", "library", "materials"],
  },
  { key: "system", views: ["settings"], utility: true },
] as const;

const ICONS: Record<WorkspaceView, string> = {
  home: "M4 10.5 12 4l8 6.5V20H4z M9 20v-6h6v6",
  observations: "M6 4h12v16H6z M9 8h6 M9 12h6 M9 16h4",
  photos: "M4 6h4l1.2-2h5.6L16 6h4v14H4z M8 13a4 4 0 1 0 8 0 4 4 0 0 0-8 0",
  learning: "M4 5h7a3 3 0 0 1 3 3v11H7a3 3 0 0 0-3 1z M20 5h-3a3 3 0 0 0-3 3v11h3a3 3 0 0 1 3 1z",
  growth: "M5 19V9 M12 19V5 M19 19v-8 M3 19h18",
  activities: "M8 4h8l1 4 3 2-2 9H6l-2-9 3-2z M9 12h6",
  search: "M4 5h10v10H4z M14 14l6 6 M16 8h4",
  discovery: "M12 3l3 6 6 3-6 3-3 6-3-6-6-3 6-3z",
  library: "M5 4h4v16H5z M10 4h4v16h-4z M16 5l3-1 3 15-3 1z",
  materials: "M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h5",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 3v2 M12 19v2 M3 12h2 M19 12h2 M5.6 5.6l1.4 1.4 M17 17l1.4 1.4 M18.4 5.6 17 7 M7 17l-1.4 1.4",
};

export function WorkspaceNav({ activeView, onChange }: WorkspaceNavProps) {
  const { activeChild } = useActiveChild();

  return (
    <nav className="workspace-nav" aria-label="GrowWise 주요 메뉴">
      <div className="workspace-nav-brand">
        <span className="workspace-brand-mark" aria-hidden="true">G</span>
        <div>
          <strong>GrowWise</strong>
          <span>Family learning workspace</span>
        </div>
      </div>

      {activeChild ? (
        <button
          type="button"
          className="workspace-child-mini"
          onClick={() => onChange("home")}
          aria-label={`${activeChild.nickname} 홈으로 이동`}
        >
          <ChildAvatar child={activeChild} size="sm" />
          <span>
            <strong>{activeChild.nickname}</strong>
            <small>현재 아이</small>
          </span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
        </button>
      ) : null}

      <div className="workspace-nav-tree">
        {WORKSPACE_GROUPS.map((group) => {
          const labelId = group.label ? `workspace-nav-group-${group.key}` : undefined;
          return (
            <section
              key={group.key}
              className={`workspace-nav-group ${group.utility ? "workspace-nav-group--utility" : ""}`}
              aria-labelledby={labelId}
            >
              {group.label ? (
                <h2 id={labelId} className="workspace-nav-group-label">
                  {group.label}
                </h2>
              ) : null}
              <ul className="workspace-nav-items">
                {group.views.map((view) => {
                  const active = activeView === view;
                  return (
                    <li key={view}>
                      <button
                        id={`workspace-nav-${view}`}
                        type="button"
                        className={`workspace-nav-item ${active ? "active" : ""}`}
                        aria-current={active ? "page" : undefined}
                        aria-controls="workspace-panel"
                        aria-label={`${WORKSPACE_LABELS[view]}: ${WORKSPACE_DESCRIPTIONS[view]}`}
                        onClick={() => onChange(view)}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d={ICONS[view]} />
                        </svg>
                        <span>{WORKSPACE_LABELS[view]}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>

      <footer className="workspace-nav-footer">
        <span>GrowWise Desktop</span>
        <small>Private by default · Local data</small>
      </footer>
    </nav>
  );
}
