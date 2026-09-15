import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { isRovingKey, nextWorkspaceIndex } from "../a11y";
import "./WorkspaceNav.css";
import { WORKSPACE_DESCRIPTIONS } from "./workspaceDescriptions";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import type { WorkspaceView } from "./workspaceTypes";
import { WORKSPACE_VIEWS } from "./workspaceViews";

type WorkspaceNavProps = {
  activeView: WorkspaceView;
  onChange: (view: WorkspaceView) => void;
};

export function WorkspaceNav({ activeView, onChange }: WorkspaceNavProps) {
  const activeIndex = Math.max(0, WORKSPACE_VIEWS.indexOf(activeView));
  const [focusIndex, setFocusIndex] = useState(activeIndex);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    setFocusIndex(activeIndex);
  }, [activeIndex]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!isRovingKey(event.key)) return;
    event.preventDefault();
    const target = nextWorkspaceIndex(focusIndex, event.key, WORKSPACE_VIEWS.length);
    setFocusIndex(target);
    itemRefs.current[target]?.focus();
  }

  return (
    <nav className="workspace-nav" aria-label="GrowWise 작업공간">
      <div className="workspace-nav-items" role="toolbar" aria-orientation="horizontal">
        {WORKSPACE_VIEWS.map((view, index) => {
          const active = activeView === view;
          return (
            <button
              key={view}
              ref={(element) => {
                itemRefs.current[index] = element;
              }}
              type="button"
              className={`workspace-nav-item ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
              aria-label={`${WORKSPACE_LABELS[view]}: ${WORKSPACE_DESCRIPTIONS[view]}`}
              tabIndex={index === focusIndex ? 0 : -1}
              onKeyDown={handleKeyDown}
              onClick={() => onChange(view)}
            >
              <span>{WORKSPACE_LABELS[view]}</span>
              <small>{WORKSPACE_DESCRIPTIONS[view]}</small>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
