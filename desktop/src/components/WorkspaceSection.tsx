import type { PropsWithChildren } from "react";

import type { WorkspaceView } from "./WorkspaceNav";

type WorkspaceSectionProps = PropsWithChildren<{
  activeView: WorkspaceView;
  view: WorkspaceView;
  className?: string;
}>;

export function WorkspaceSection({
  activeView,
  view,
  className,
  children,
}: WorkspaceSectionProps) {
  if (activeView !== view) return null;

  return (
    <section className={className} data-workspace-view={view}>
      {children}
    </section>
  );
}
