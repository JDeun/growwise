import type { GeneratedMaterial } from "../api";
import { materialPresentationTemplate } from "../material-presentation";
import { MaterialContent } from "./MaterialContent";
import "./MaterialParentGuide.css";

export function MaterialParentGuide({ material }: { material: GeneratedMaterial }) {
  const guide = material.parent_guide_markdown?.trim() ?? "";
  const presentation = materialPresentationTemplate(material.kind);

  return (
    <div className="material-support-pages">
      {guide && (
        <details className="material-parent-guide" open>
          <summary>
            <span>부모용 교안 · 진행 안내</span>
            <small>준비 · 진행 · 관찰 · 활동 후 기록</small>
          </summary>
          <div className="material-parent-guide-content">
            <MaterialContent markdown={guide} />
          </div>
        </details>
      )}

      <section
        className="material-presentation-template"
        data-material-kind={presentation.kind}
        data-presentation-layout={presentation.layout}
        aria-label={`${presentation.label} 인쇄 양식`}
      >
        <header>
          <p className="material-presentation-kicker">GROWWISE WORKSHEET</p>
          <h3>{presentation.label}</h3>
          <p>{presentation.purpose}</p>
        </header>
        {guide && (
          <section className="material-presentation-guide" aria-label="부모용 진행 안내">
            <strong>진행 안내</strong>
            <MaterialContent markdown={guide} />
          </section>
        )}
        <div className="material-presentation-zones">
          {presentation.zones.map((zone, index) => (
            <section key={zone} className="material-presentation-zone">
              <div className="material-presentation-zone-heading">
                <span>{index + 1}</span>
                <strong>{zone}</strong>
              </div>
              <div className="material-presentation-writing-space" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
            </section>
          ))}
        </div>
        <footer>
          <span>날짜 ____________________</span>
          <span>다음에 이어볼 것 ________________________________________</span>
        </footer>
      </section>
    </div>
  );
}
