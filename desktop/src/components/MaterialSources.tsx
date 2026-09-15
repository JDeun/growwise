import type { ResourceRecord } from "../api";
import { EmptyState } from "./EmptyState";

interface MaterialSourcesProps {
  sourceRefs: string[];
  resources?: ResourceRecord[];
  headingId?: string;
}

const RESOURCE_PREFIX = "resource:";

// A source ref is either a `resource:<id>` pointer into the parent's own library or an external
// provenance token (e.g. `osm:place:123`). Resolve library refs to a human title; show external
// refs verbatim so provenance stays transparent for parent review.
function refLabel(ref: string, resources: ResourceRecord[]): string {
  if (!ref.startsWith(RESOURCE_PREFIX)) return ref;
  const id = ref.slice(RESOURCE_PREFIX.length);
  return resources.find((resource) => resource.id === id)?.title ?? "연결된 내 자료";
}

/**
 * Read-only display of a material's source references / citations for parent review.
 * Standalone and additive: no generation or review side effects.
 */
export function MaterialSources({ sourceRefs, resources = [], headingId = "material-sources-title" }: MaterialSourcesProps) {
  // De-duplicate defensively; refs may arrive repeated from different generation passes.
  const refs = Array.from(new Set(sourceRefs));

  return (
    <section className="material-sources-block" aria-labelledby={headingId}>
      <p className="eyebrow" id={headingId}>출처 · 근거</p>
      {refs.length === 0 ? (
        <EmptyState
          title="연결된 출처가 없습니다."
          description="이 자료는 특정 자료를 근거로 지정하지 않고 만들어졌습니다. 필요하면 내 자료를 선택해 다시 생성할 수 있습니다."
        />
      ) : (
        <ul className="material-sources" role="list" aria-label="이 자료의 출처 목록">
          {refs.map((ref) => (
            <li key={ref}>
              <span title={ref}>{refLabel(ref, resources)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
