import type { CurriculumTarget } from "../api";
import "./MaterialCurriculumTargets.css";

interface MaterialCurriculumTargetsProps {
  targets?: CurriculumTarget[];
}

export function MaterialCurriculumTargets({ targets = [] }: MaterialCurriculumTargetsProps) {
  if (targets.length === 0) return null;

  return (
    <details className="material-curriculum-targets">
      <summary>교육과정 연결 {targets.length}개</summary>
      <div className="material-curriculum-list">
        {targets.map((target) => (
          <article key={target.mapping_id}>
            <div>
              <strong>{target.domain}</strong>
              <span>{target.framework}</span>
            </div>
            <p>{target.description}</p>
            <small>
              {target.source_ref}
              {target.standard_codes.length > 0
                ? ` · 성취기준 ${target.standard_codes.join(", ")}`
                : " · 영역/교과 수준 매핑"}
            </small>
          </article>
        ))}
      </div>
    </details>
  );
}
