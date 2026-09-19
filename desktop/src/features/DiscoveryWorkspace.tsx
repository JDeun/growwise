import { FormEvent, useEffect, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  discoverEducationResources,
  parseDiscoveryLocation,
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
  reference: "백과·역사",
  science: "과학·자연",
  language: "언어·어휘",
  media: "공개 미디어",
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
      return "일반 주제어 필요";
    case "needs_location":
      return "위치 입력 시 사용";
    case "unavailable":
      return "현재 사용할 수 없음";
    case "disabled":
      return "확장 검색 꺼짐";
    case "available":
      return "연결 가능";
    case "configured":
      return "설정됨";
    case "catalog_link":
      return "공식 카탈로그 링크";
    case "offline_dataset":
      return "오프라인 데이터셋";
    case "local_optional":
      return "선택 로컬 엔진";
    case "renderer":
      return "로컬 렌더러";
    default:
      return status;
  }
}

type Props = { active: boolean };

export function DiscoveryWorkspace({ active }: Props) {
  const { children, activeChildId: childId, selectChild, syncRememberedChild } = useActiveChild();
  const [query, setQuery] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
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
    setLatitude("");
    setLongitude("");
    setNotice(null);
    setError(null);
  }, [childId]);

  async function handleDiscover(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId || busy) return;
    setError(null);
    setNotice(null);

    let location;
    try {
      location = parseDiscoveryLocation(latitude, longitude);
    } catch (locationError) {
      setError(errorMessage(locationError));
      return;
    }

    setBusy(true);
    try {
      const response = await discoverEducationResources(childId, query, location);
      setResult(response);
      if (response.suggestions.length === 0) {
        setNotice("현재 조건에서 바로 제안할 공개 자료를 찾지 못했습니다. 검색어나 탐방 위치를 바꿔보세요.");
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
        "참고 자료에 저장했습니다. 이제 이 자료를 검색 근거로 쓰거나 자료 생성 화면에서 선택할 수 있습니다.",
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
              관심사와 최근 기록은 로컬에서 후보 순위를 정하는 데 사용합니다. 외부 공개 소스에는
              허용된 일반 교육 주제어만 전달하며 아이 이름, ID, 관찰 원문, 자유 입력 문장은 보내지 않습니다.
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
            <small className="muted">
              입력한 문장 전체를 외부로 보내지 않습니다. 외부 검색에는 인식된 일반 교육 주제어만 사용합니다.
            </small>
          </label>

          <details className="discovery-location-options">
            <summary>주변 탐방 장소도 찾기 · 선택</summary>
            <p className="muted">
              부모가 직접 입력한 좌표가 있을 때만 OpenStreetMap Overpass에 위치를 전송합니다.
              좌표는 아이 프로필에 저장하지 않습니다.
            </p>
            <div className="discovery-location-grid">
              <label>
                <span>위도</span>
                <input
                  type="number"
                  min="-90"
                  max="90"
                  step="any"
                  inputMode="decimal"
                  value={latitude}
                  onChange={(event) => setLatitude(event.target.value)}
                  placeholder="예: 37.2636"
                  disabled={busy}
                />
              </label>
              <label>
                <span>경도</span>
                <input
                  type="number"
                  min="-180"
                  max="180"
                  step="any"
                  inputMode="decimal"
                  value={longitude}
                  onChange={(event) => setLongitude(event.target.value)}
                  placeholder="예: 127.0286"
                  disabled={busy}
                />
              </label>
            </div>
            {(latitude || longitude) && (
              <button
                className="quiet-button"
                type="button"
                onClick={() => {
                  setLatitude("");
                  setLongitude("");
                }}
                disabled={busy}
              >
                탐방 위치 지우기
              </button>
            )}
          </details>

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
              <div className="discovery-source-summary">
                <div>
                  <h3>교육 소스</h3>
                  <p className="muted">
                    {result.sources.filter((source) =>
                      ["live", "fresh", "stale", "ready"].includes(source.status),
                    ).length}개 소스가 이번 검색에 응답했습니다.
                  </p>
                </div>
                <span>{result.sources.length}개 연동 카탈로그</span>
              </div>

              <div className="discovery-source-list discovery-source-list--active">
                {result.sources
                  .filter((source) =>
                    ["live", "fresh", "stale", "ready"].includes(source.status),
                  )
                  .map((source) => (
                    <div key={source.source}>
                      <strong>{source.label ?? SOURCE_LABEL[source.source] ?? source.source}</strong>
                      <span>{sourceStatusText(source.status)}</span>
                    </div>
                  ))}
              </div>

              <details className="discovery-source-catalog">
                <summary>전체 교육 소스와 연결 상태 보기</summary>
                <div className="discovery-source-list">
                  {result.sources.map((source) => (
                    <div key={source.source}>
                      <div className="discovery-source-name">
                        <strong>{source.label ?? SOURCE_LABEL[source.source] ?? source.source}</strong>
                        {source.mode && <small>{source.mode}</small>}
                      </div>
                      <div className="discovery-source-actions">
                        <span>{sourceStatusText(source.status)}</span>
                        {source.homepage && (
                          <a href={source.homepage} target="_blank" rel="noreferrer">
                            공식 사이트
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </details>

              <p className="muted">
                아이 이름, ID, 관찰 원문은 외부 소스에 보내지 않습니다. 텍스트 검색에는 일반화된
                주제어만 사용하고, 부모가 직접 좌표를 입력한 경우에만 위치 기반 소스에 좌표를 전송합니다.
              </p>
            </section>

            <section className="discovery-results" aria-live="polite">
              <div className="section-heading">
                <div>
                  <h3>후보 {result.suggestions.length}건</h3>
                  {result.query && <p className="muted">외부 일반화 검색어: {result.query}</p>}
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
                            ? "참고 자료에 저장됨"
                            : savingId === suggestion.candidate_id
                              ? "저장 중…"
                              : "참고 자료에 저장"}
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
