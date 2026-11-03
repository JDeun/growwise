import type { GeneratedMaterial, Stage } from "../api";
import { materialPresentationTemplate } from "../material-presentation";
import { MaterialContent } from "./MaterialContent";
import "./MaterialParentGuide.css";
import "./MaterialPresentation.css";

export function MaterialParentGuide({ material, stage }: { material: GeneratedMaterial; stage?: Stage }) {
  const guide = material.parent_guide_markdown?.trim() ?? "";
  const presentation = materialPresentationTemplate(material.kind);
  const modelAuthored = material.generator_mode === "llm_enhanced";
  const reviewTime = material.reviewed_at ? Date.parse(material.reviewed_at) : NaN;
  const hasProvenance = material.generator_version || material.model_id || Number.isFinite(reviewTime);
  const providerLabel = material.model_provider === "OllamaProvider" ? "Ollama"
    : material.model_provider === "OpenAICompatibleProvider" ? "OpenAI 호환" : material.model_provider;

  return (
    <div className="material-support-pages">
      {(guide || hasProvenance) && (
        <details className="material-parent-guide">
          <summary>
            <span>부모용 교안 · 진행 안내</span>
            <small>준비 · 진행 · 힌트 · 관찰 · 난이도 · 안전 · 기록</small>
          </summary>
          <div className="material-parent-guide-content">
            {guide && <MaterialContent markdown={guide} />}
            {hasProvenance && <dl className="material-provenance" aria-label="자료 생성·검토 정보">
              <div><dt>작성 방식</dt><dd>{material.generator_mode === "parent_edit"
                ? "이전 자료를 부모가 직접 수정" : modelAuthored ? "AI 보강" : "기본 활동 구성"}</dd></div>
              {modelAuthored && material.model_id && <div><dt>사용 모델</dt><dd>
                {providerLabel ? `${providerLabel} · ` : ""}{material.model_id}
              </dd></div>}
              {material.generator_version && <div><dt>생성 규칙 버전</dt><dd>{material.generator_version}</dd></div>}
              {material.review_decision && <div><dt>부모 결정</dt><dd>{({ approved: "사용 승인",
                rejected: "사용 안 함", revision_requested: "수정 요청" })[material.review_decision]}</dd></div>}
              {Number.isFinite(reviewTime) && <div><dt>부모 결정 시각</dt><dd>{new Date(reviewTime).toLocaleString("ko-KR")}</dd></div>}
            </dl>}
          </div>
        </details>
      )}

      {stage !== "infant_0_2" && <section
        className="material-presentation-template"
        data-material-kind={presentation.kind}
        data-presentation-layout={presentation.layout}
        aria-label={`${presentation.label} 인쇄 양식`}
      >
        <header>
          <h3>{presentation.label}</h3>
          <p>{presentation.purpose}</p>
        </header>
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
      </section>}
    </div>
  );
}
