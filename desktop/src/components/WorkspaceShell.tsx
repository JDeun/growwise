import { useEffect, useState, type ReactNode } from "react";

import { useOptionalActiveChild } from "../active-child-context";
import { listActivities, listMaterials, listPhotoRecords } from "../api";
import { ChildAvatar } from "./ChildAvatar";
import "./WorkspaceShell.css";
import { WorkspaceNav } from "./WorkspaceNav";
import { WORKSPACE_LABELS } from "./workspaceLabels";
import { readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";
import type { WorkspaceView } from "./workspaceTypes";

type NotificationItem = {
  view: "materials" | "photos";
  label: string;
  count: number;
};

type NotificationState =
  | { kind: "idle"; items: NotificationItem[] }
  | { kind: "loading"; items: NotificationItem[] }
  | { kind: "ready"; items: NotificationItem[] }
  | { kind: "error"; items: NotificationItem[] };

type WorkspaceShellProps = {
  initialView?: WorkspaceView;
  renderWorkspace: (
    activeView: WorkspaceView,
    navigate: (view: WorkspaceView) => void,
  ) => ReactNode;
};

export function WorkspaceShell({ initialView, renderWorkspace }: WorkspaceShellProps) {
  const activeChild = useOptionalActiveChild()?.activeChild ?? null;
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationState, setNotificationState] = useState<NotificationState>({
    kind: "idle",
    items: [],
  });
  const [activeView, setActiveView] = useState<WorkspaceView>(() => {
    if (initialView) return initialView;
    if (typeof window === "undefined") return "home";
    return readWorkspaceView(window.localStorage);
  });

  function handleChange(view: WorkspaceView) {
    setNotificationsOpen(false);
    setActiveView(view);
    if (typeof window !== "undefined") writeWorkspaceView(window.localStorage, view);
  }

  useEffect(() => {
    let cancelled = false;
    const childId = activeChild?.id;

    if (!childId) {
      setNotificationState({ kind: "ready", items: [] });
      return () => {
        cancelled = true;
      };
    }

    setNotificationState((current) => ({ kind: "loading", items: current.items }));
    void Promise.allSettled([
      listMaterials(childId),
      listPhotoRecords(childId),
      listActivities(childId),
    ]).then(([materialsResult, photosResult, activitiesResult]) => {
      if (cancelled) return;

      const items: NotificationItem[] = [];
      if (materialsResult.status === "fulfilled") {
        const count = materialsResult.value.filter((material) =>
          ["draft", "review_pending", "revision_requested"].includes(material.status),
        ).length;
        if (count > 0) items.push({ view: "materials", label: "검토할 학습 자료", count });
      }
      if (photosResult.status === "fulfilled") {
        const count = photosResult.value.filter((record) =>
          ["draft", "failed"].includes(record.status),
        ).length;
        if (count > 0) items.push({ view: "photos", label: "확인할 사진 기록", count });
      }
      if (activitiesResult.status === "fulfilled") {
        const count = activitiesResult.value.filter((activity) => activity.status === "active").length;
        if (count > 0) items.push({ view: "materials", label: "진행 중인 활동", count });
      }

      const allFailed =
        materialsResult.status === "rejected"
        && photosResult.status === "rejected"
        && activitiesResult.status === "rejected";
      setNotificationState({ kind: allFailed ? "error" : "ready", items });
    });

    return () => {
      cancelled = true;
    };
  }, [activeChild?.id, activeView, notificationsOpen]);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k") return;
      event.preventDefault();
      setActiveView("conversation");
      writeWorkspaceView(window.localStorage, "conversation");
      window.requestAnimationFrame(() => {
        document.querySelector<HTMLElement>(
          ".conversation-composer input, .conversation-search-tools input",
        )?.focus();
      });
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const notificationCount = notificationState.items.reduce(
    (sum, item) => sum + item.count,
    0,
  );

  return (
    <div className="workspace-shell-root">
      <a className="skip-link" href="#workspace-panel">
        작업공간 본문으로 바로가기
      </a>
      <WorkspaceNav activeView={activeView} onChange={handleChange} />
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-topbar-actions">
            <button
              type="button"
              className="workspace-search-trigger"
              onClick={() => handleChange("conversation")}
              aria-label="대화와 기록 검색으로 이동"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>
              <span>검색어를 입력하세요...</span>
            </button>

            <div className="workspace-notifications">
              <button
                type="button"
                className="workspace-icon-button"
                aria-label={notificationCount > 0 ? `알림 ${notificationCount}건` : "알림"}
                aria-expanded={notificationsOpen}
                aria-controls="workspace-notification-popover"
                onClick={() => setNotificationsOpen((current) => !current)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6.5 9.5a5.5 5.5 0 0 1 11 0c0 6 2.2 6.5 2.2 6.5H4.3s2.2-.5 2.2-6.5Z"/>
                  <path d="M10 19h4"/>
                </svg>
                {notificationState.items.length > 0 && (
                  <span className="workspace-notification-badge" aria-hidden="true">
                    {notificationCount}
                  </span>
                )}
              </button>
              {notificationsOpen && (
                <div
                  id="workspace-notification-popover"
                  className="workspace-notification-popover"
                  role="dialog"
                  aria-label="알림"
                >
                  <div className="workspace-notification-heading">
                    <strong>알림</strong>
                    {notificationState.items.length > 0 && (
                      <span>{notificationCount}건</span>
                    )}
                  </div>
                  {notificationState.kind === "loading" && notificationState.items.length === 0 ? (
                    <p>확인할 항목을 불러오는 중입니다.</p>
                  ) : notificationState.kind === "error" ? (
                    <p>알림을 불러오지 못했습니다. 각 작업공간에서 직접 확인할 수 있습니다.</p>
                  ) : notificationState.items.length === 0 ? (
                    <p>{activeChild ? "지금 확인할 새 항목이 없습니다." : "아이 프로필을 선택하면 확인할 항목을 알려드립니다."}</p>
                  ) : (
                    <div className="workspace-notification-list">
                      {notificationState.items.map((item) => (
                        <button
                          type="button"
                          key={`${item.view}-${item.label}`}
                          onClick={() => handleChange(item.view)}
                        >
                          <span>{item.label}</span>
                          <strong>{item.count}</strong>
                          <em aria-hidden="true">›</em>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <button
              type="button"
              className="workspace-topbar-avatar"
              onClick={() => handleChange("profile")}
              aria-label="아이 프로필로 이동"
            >
              <ChildAvatar child={activeChild} size="sm" />
            </button>
          </div>
        </header>
        <div
          id="workspace-panel"
          className="workspace-shell"
          role="region"
          aria-label={`${WORKSPACE_LABELS[activeView]} 작업공간`}
          tabIndex={-1}
          data-active-workspace={activeView}
        >
          {renderWorkspace(activeView, handleChange)}
        </div>
      </main>
    </div>
  );
}
