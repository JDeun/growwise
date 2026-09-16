import { FormEvent, useEffect, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  discoverEducationResources,
  saveDiscoveredResource,
  type DiscoveryCategory,
  type DiscoveryResponse,
  type DiscoverySuggestion,
} from "../discovery-api";
import "./DiscoveryWorkspace.css";

const CATEGORY_LABEL: Record<DiscoveryCategory, string> = {
  book: "도서",
  curriculum: "교육과정",
  place: "탐방",
};

const SOURCE_LABEL: Record<string, string> = {
  data4library: "도서관 정보나루",
  kr_official_curriculum_catalog: "공식 교육과정",
  public_curriculum: "공공 교육과정 API",
  openstreetmap_overpass: "OpenStreetMap 탐방 장소",
};

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return typeof error === "string" ? error : "교육 자료를 찾지 못했습니다.";
}

function sourceStatusText(status: string): string {
  switch (status) {
    case "live":
      return "새로 조회함";
    case "fresh":
      return "저장된 최신 결과";
    case "stale":
      return "이전에 저장된 결과";
    case "not_configured":
      return "설정 필요";
    case "needs_query":
      return "검색어 필요";
    case "needs_location":
      return "위치 입력 시 사용";
    case "unavailable":
      return "현재 사용할 수 없음";
    default:
      return status;
  }
}

type Props = { active: boolean };

export function DiscoveryWorkspace({ active }: Props) {
  const { children, activeChildId: childId, selectChild, syncRememberedChild } = useActiveChild();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<DiscoveryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    syncRememberedChild();
  }, [active, syncRememberedChild]);

  useEffect(() => {
    setResult(null);
    setSavedIds(new Set());
    setNotice(null);
    setError(null);
  }, [childId]);

  async function handleDiscover(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const response = await discoverEducationResources(childId, query);
      setResult(response);
      if (response.suggestions.length === 0) {
        setNotice("현재 조건에서 바로 제안할 공개 자료를 찾지 못했습니다. 검색어를 바꿔보세요.");
      } else if (!query.trim() && response.query_terms.length > 0) {
        setNotice(
          `최근 기록에서 ${response.query_terms.slice(0, 4).join(", ")} 맥락을 찾아 후보를 구성했습니다.`,
        );
      }
    } catch (discoverError) {
      setError(errorMessage(discoverError));
    } finally {
      setBusy(false);
    }
  }

  async function handleSave(suggestion: DiscoverySuggestion) {
    if (!childId || savingId) return;
    setSavingId(suggestion.candidate_id);
    setError(null);
    try {
      await saveDiscoveredResource(childId, suggestion);
      setSavedIds((current) => new Set(current).add(suggestion.candidate_id));
      setNotice(
        "라이브러리에 저장했습니다. 이제 이 자료를 검색 근거로 쓰거나 자료 생성 화면에서 선택할 수 있습니다.",
      );
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSavingId(null);
    }
  }

  if (!active) return null;

  return (
    <main className="discovery-workspace app-shell" aria-labelledby="discovery-title">
      <section className="workspace discovery-card">
        <div className="section-heading">
          <div>
            <p className="card-label">교육 자료 발견</p>
            <h2 id="discovery-title">아이의 현재 맥락에서 다음 자료 찾기</h2>
            <p className="muted">
              관심사와 최근 기록에서 일반 검색어만 로컬로 뽑아 공개 교육 자원을 찾습니다. 아이 이름,
              ID, 관찰 원문은 외부 API로 보내지 않습니다.
            </p>
          </div>
        </div>

        <form className="discovery-form" onSubmit={handleDiscover}>
          <label>
            <span>아이</span>
            <select
              value={childId}
              onChange={(event) => selectChild(event.target.value)}
              disabled={busy || children.length === 0}
            >
              {children.length === 0 && <option value="">먼저 아이 프로필을 만들어주세요</option>}
              {children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.nickname || child.id}
                </option>
              ))}
            </select>
          </label>
          <label className="discovery-query-field">
            <span>찾고 싶은 주제 · 선택</span>
            <input
              value={query}
              maxLength={200}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="비워두면 관심사와 최근 기록을 바탕으로 찾습니다. 예: 공룡, 우주, 측정"
            />
          </label>
          <button className="primary-button" type="submit" disabled={!childId || busy}>
            {busy ? "공개 자료 확인 중…" : "교육 자료 찾기"}
          </button>
        </form>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="operation-notice" role="status" aria-live="polite">
            {notice}
          </p>
        )}

        {result && (
          <>
            <section className="discovery-source-status" aria-label="자료 출처 상태">
              <h3>자료 출처</h3>
              <div className="discovery-source-list">
                {result.sources.map((source) => (
                  <div key={source.source}>
                    <strong>{SOURCE_LABEL[source.source] ?? source.source}</strong>
                    <span>{sourceStatusText(source.status)}</span>
                  </div>
                ))}
              </div>
              <p className="muted">
                외부 서비스가 꺼져 있어도 공식 교육과정 메타데이터와 이미 저장한 라이브러리는 계속
                사용할 수 있습니다.
              </p>
            </section>

            <section className="discovery-results" aria-live="polite">
              <div className="section-heading">
                <div>
                  <h3>후보 {result.suggestions.length}건</h3>
                  {result.query && <p className="muted">외부 검색어: {result.query}</p>}
                </div>
              </div>
              {result.suggestions.length === 0 ? (
                <p className="muted">저장할 후보가 없습니다.</p>
              ) : (
                <div className="discovery-grid">
                  {result.suggestions.map((suggestion) => {
                    const saved = savedIds.has(suggestion.candidate_id);
                    return (
                      <article className="discovery-result-card" key={suggestion.candidate_id}>
                        <div className="discovery-result-heading">
                          <span className="badge">{CATEGORY_LABEL[suggestion.category]}</span>
                          <small>{SOURCE_LABEL[suggestion.source_name] ?? suggestion.source_name}</small>
                        </div>
                        <h4>{suggestion.title}</h4>
                        {suggestion.summary && <p>{suggestion.summary}</p>}
                        <p className="muted">{suggestion.rationale}</p>
                        <details>
                          <summary>출처와 이용 조건</summary>
                          <p>{suggestion.attribution}</p>
                          <p>{suggestion.license_note}</p>
                          {suggestion.source_url && (
                            <a href={suggestion.source_url} target="_blank" rel="noreferrer">
                              원 출처 열기
                            </a>
                          )}
                        </details>
                        <button
                          className="quiet-button"
                          type="button"
                          disabled={saved || savingId !== null}
                          onClick={() => void handleSave(suggestion)}
                        >
                          {saved
                            ? "라이브러리에 저장됨"
                            : savingId === suggestion.candidate_id
                              ? "저장 중…"
                              : "라이브러리에 저장"}
                        </button>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
