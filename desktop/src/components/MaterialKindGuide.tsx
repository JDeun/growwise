import type { MaterialCatalogItem } from "../material-catalog";

interface MaterialKindGuideProps {
  item: MaterialCatalogItem;
}

export function MaterialKindGuide({ item }: MaterialKindGuideProps) {
  return (
    <section className="material-kind-guide" aria-label={`${item.label} 생성 가이드`}>
      <div className="material-kind-guide-flow">
        <span className="card-label">권장 흐름</span>
        <ol>
          {item.flow.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
      <div className="material-kind-guide-review">
        <span className="card-label">부모 검토 포인트</span>
        <ul>
          {item.reviewPoints.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
