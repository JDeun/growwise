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
    label: "기록",
    views: ["observations", "photos", "learning"],
  },
  {
    key: "growth",
    label: "성장과 활동",
    views: ["growth", "activities"],
  },
  {
    key: "resources",
    label: "찾기와 자료",
    views: ["search", "discovery", "library", "materials"],
  },
  { key: "system", views: ["settings"], utility: true },
] as const;

export function WorkspaceNav({ activeView, onChange }: WorkspaceNavProps) {
  return (
    <nav className="workspace-nav" aria-label="GrowWise 주요 메뉴">
      <div className="workspace-nav-brand" aria-hidden="true">
        <strong>메뉴</strong>
        <span>기록·성장·자료를 목적별로 찾습니다.</span>
      </div>

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
                        <span>{WORKSPACE_LABELS[view]}</span>
                        <small>{WORKSPACE_DESCRIPTIONS[view]}</small>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
    </nav>
  );
}
