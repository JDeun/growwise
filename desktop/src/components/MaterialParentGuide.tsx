import type { GeneratedMaterial } from "../api";
import { MaterialContent } from "./MaterialContent";
import "./MaterialParentGuide.css";

export function MaterialParentGuide({ material }: { material: GeneratedMaterial }) {
  const guide = material.parent_guide_markdown?.trim();
  if (!guide) return null;

  return (
    <details className="material-parent-guide" open>
      <summary>
        <span>부모용 교안 · 진행 안내</span>
        <small>준비 · 진행 · 관찰 · 활동 후 기록</small>
      </summary>
      <div className="material-parent-guide-content">
        <MaterialContent markdown={guide} />
      </div>
    </details>
  );
}
