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
  reference: "백과·사실",
  science: "과학",
  nature: "자연·생물",
  media: "공개 이미지",
};

const SOURCE_LABEL: Record<string, string> = {
  curated_education_catalog: "공식 교육 콘텐츠 링크",
  data4library: "도서관 정보나루",
  national_library_isbn: "국립중앙도서관 ISBN 서지",
  open_library: "Open Library",
  google_books: "Google Books",
  kr_official_curriculum_catalog: "공식 교육과정",
  public_curriculum: "공공 교육과정 API",
  krdict: "한국어기초사전",
  wikipedia_ko: "한국어 Wikipedia",
  wikidata: "Wikidata",
  wikimedia_commons: "Wikimedia Commons",
  nasa_images: "NASA Images",
  gbif_species: "GBIF 생물 분류",
  korean_heritage_palaces: "국가유산청 궁궐·문화유산",
  openstreetmap_overpass: "OpenStreetMap 탐방 장소",
  korea_museum_standard: "전국 박물관·미술관",
  kma_weather: "기상청 현재 날씨",
};

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return typeof error === "string" ? error : "교육 자료를 찾지 못했습니다.";
}

function sourceStatusText(status: string): string {
  switch (status) {
    case "live":
      return "새로 조회함";
    case "ready":
      return "사용 가능";
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
    case "not_relevant":
      return "현재 주제에서는 생략";
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
        "참고 자료에 저장했습니다. 이제 검색 근거로 쓰거나 활동 자료 생성 시 근거로 선택할 수 있습니다.",
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
                외부 서비스가 꺼져 있어도 공식 교육과정 메타데이터와 이미 저장한 참고 자료는 계속
                사용할 수 있습니다. 여러 공개 소스는 주제 관련성이 있을 때만 호출합니다. 탐방 위치를 입력한 경우에만 해당 좌표가 Overpass 요청에 포함됩니다.
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
