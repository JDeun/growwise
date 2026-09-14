import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  CoreApiError,
  appendConversationTurn,
  createChild,
  createConversation,
  createObservation,
  createResource,
  getCoreRuntimeStatus,
  getGrowthMap,
  getHealth,
  getInfantActivities,
  listChildren,
  listObservations,
  listResources,
  searchChildContext,
  type ChildProfile,
  type ConversationAnswer,
  type ConversationSession,
  type CoreRuntimeStatus,
  type ExperienceAxis,
  type GrowthMap,
  type HealthResponse,
  type InfantActivitySuggestions,
  type LearningLog,
  type ResourceKind,
  type ResourceRecord,
  type SearchResponse,
} from "./api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse; runtime: CoreRuntimeStatus }
  | { kind: "offline"; message: string };

const LAST_CHILD_KEY = "growwise:last-child-id";
const AXIS_OPTIONS: Array<{ value: ExperienceAxis; label: string }> = [
  { value: "physical", label: "신체" },
  { value: "emotional_character", label: "정서·인성" },
  { value: "expression_art", label: "표현·예술" },
  { value: "thinking_inquiry", label: "사고·탐구" },
  { value: "social", label: "사회성" },
  { value: "reading", label: "읽기" },
  { value: "speaking", label: "말하기" },
  { value: "exploration", label: "탐색" },
];

function resultText(result: Record<string, unknown>): string {
  const observation = result.parent_observation;
  if (typeof observation === "string") return observation;
  const title = result.title;
  if (typeof title === "string") return title;
  return "관련 기록";
}

function App() {
  const [connection, setConnection] = useState<ConnectionState>({ kind: "loading" });
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [activeChild, setActiveChild] = useState<ChildProfile | null>(null);
  const [growthMap, setGrowthMap] = useState<GrowthMap | null>(null);
  const [timeline, setTimeline] = useState<LearningLog[]>([]);
  const [nickname, setNickname] = useState("");
  const [ageMonths, setAgeMonths] = useState("9");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [observation, setObservation] = useState("");
  const [selectedAxes, setSelectedAxes] = useState<ExperienceAxis[]>([]);
  const [observationSaving, setObservationSaving] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [activities, setActivities] = useState<InfantActivitySuggestions | null>(null);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationSession | null>(null);
  const [conversationAnswers, setConversationAnswers] = useState<ConversationAnswer[]>([]);
  const [conversationQuestion, setConversationQuestion] = useState("");
  const [conversationBusy, setConversationBusy] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [resources, setResources] = useState<ResourceRecord[]>([]);
  const [resourceKind, setResourceKind] = useState<ResourceKind>("note");
  const [resourceTitle, setResourceTitle] = useState("");
  const [resourceContent, setResourceContent] = useState("");
  const [resourceSaving, setResourceSaving] = useState(false);
  const [resourceError, setResourceError] = useState<string | null>(null);

  const loadChildContext = useCallback(async (child: ChildProfile) => {
    const [map, logs, childResources] = await Promise.all([
      getGrowthMap(child.id),
      listObservations(child.id),
      listResources(child.id),
    ]);
    setActiveChild(child);
    setGrowthMap(map);
    setTimeline(logs);
    setResources(childResources);
    setActivities(null);
    setSearchResult(null);
    setConversation(null);
    setConversationAnswers([]);
    localStorage.setItem(LAST_CHILD_KEY, child.id);
  }, []);

  const refresh = useCallback(async () => {
    setConnection({ kind: "loading" });
    try {
      const [health, runtime, storedChildren] = await Promise.all([
        getHealth(),
        getCoreRuntimeStatus(),
        listChildren(),
      ]);
      setConnection({ kind: "connected", health, runtime });
      setChildren(storedChildren);
      if (storedChildren.length > 0) {
        const rememberedId = localStorage.getItem(LAST_CHILD_KEY);
        const selected = storedChildren.find((child) => child.id === rememberedId) ?? storedChildren[0];
        await loadChildContext(selected);
      } else {
        setActiveChild(null);
        setGrowthMap(null);
        setTimeline([]);
        setResources([]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "GrowWise Core 상태를 확인할 수 없습니다.";
      setConnection({ kind: "offline", message });
    }
  }, [loadChildContext]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function handleCreateChild(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedNickname = nickname.trim();
    const parsedAge = Number.parseInt(ageMonths, 10);
    if (!trimmedNickname) return setFormError("아이를 구분할 닉네임을 입력해 주세요.");
    if (!Number.isFinite(parsedAge) || parsedAge < 0 || parsedAge > 24) return setFormError("월령은 0~24개월로 입력해 주세요.");
    setSaving(true); setFormError(null);
    try {
      const child = await createChild({ nickname: trimmedNickname, stage: "infant_0_2", age_months: parsedAge, interests: [] });
      setChildren((current) => [child, ...current.filter((item) => item.id !== child.id)]);
      await loadChildContext(child);
      setNickname("");
    } catch (error) { setFormError(error instanceof Error ? error.message : "프로필 저장에 실패했습니다."); }
    finally { setSaving(false); }
  }

  async function handleSelectChild(childId: string) {
    const child = children.find((item) => item.id === childId);
    if (!child) return;
    try { await loadChildContext(child); }
    catch (error) { setFormError(error instanceof Error ? error.message : "아이 정보를 불러오지 못했습니다."); }
  }

  async function handleCreateObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const text = observation.trim();
    if (!text) return setObservationError("기억할 가치가 있는 관찰을 짧게 적어 주세요.");
    setObservationSaving(true); setObservationError(null);
    try {
      await createObservation({ child_id: activeChild.id, observation: text, experience_axes: selectedAxes });
      const [map, logs] = await Promise.all([getGrowthMap(activeChild.id), listObservations(activeChild.id)]);
      setGrowthMap(map); setTimeline(logs); setObservation(""); setSelectedAxes([]); setActivities(null); setSearchResult(null);
    } catch (error) { setObservationError(error instanceof Error ? error.message : "관찰 기록 저장에 실패했습니다."); }
    finally { setObservationSaving(false); }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const query = searchQuery.trim();
    if (query.length < 2) return setSearchError("두 글자 이상으로 검색해 주세요.");
    setSearching(true); setSearchError(null);
    try { setSearchResult(await searchChildContext(activeChild.id, query)); }
    catch (error) { setSearchError(error instanceof Error ? error.message : "검색에 실패했습니다."); }
    finally { setSearching(false); }
  }

  async function handleConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const question = conversationQuestion.trim();
    if (question.length < 2) return setConversationError("두 글자 이상으로 질문해 주세요.");
    setConversationBusy(true); setConversationError(null);
    try {
      let session = conversation;
      if (!session) {
        session = await createConversation(activeChild.id);
        setConversation(session);
      }
      const answer = await appendConversationTurn(session.id, question);
      setConversationAnswers((current) => [...current, answer]);
      setConversationQuestion("");
    } catch (error) { setConversationError(error instanceof Error ? error.message : "후속 질문 처리에 실패했습니다."); }
    finally { setConversationBusy(false); }
  }

  async function handleCreateResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const title = resourceTitle.trim();
    const content = resourceContent.trim();
    if (!title) return setResourceError("자료 제목을 입력해 주세요.");
    setResourceSaving(true); setResourceError(null);
    try {
      await createResource({
        kind: resourceKind,
        title,
        child_id: activeChild.id,
        summary: null,
        content: content || null,
        source_url: null,
        source_name: "parent",
        author: null,
        tags: [],
        stage_tags: [activeChild.stage],
        provenance: { origin: "desktop_manual" },
      });
      setResources(await listResources(activeChild.id));
      setResourceTitle(""); setResourceContent("");
    } catch (error) { setResourceError(error instanceof Error ? error.message : "자료 저장에 실패했습니다."); }
    finally { setResourceSaving(false); }
  }

  async function handleLoadActivities() {
    if (!activeChild) return;
    setActivitiesLoading(true); setActivitiesError(null);
    try { setActivities(await getInfantActivities(activeChild.id)); }
    catch (error) { setActivitiesError(error instanceof Error ? error.message : "활동 후보를 불러오지 못했습니다."); }
    finally { setActivitiesLoading(false); }
  }

  function toggleAxis(axis: ExperienceAxis) {
    setSelectedAxes((current) => current.includes(axis) ? current.filter((item) => item !== axis) : [...current, axis]);
  }

  const isConnected = connection.kind === "connected";
  const mode = isConnected ? connection.health.operation_mode : null;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><img className="brand-logo" src="/growwise-symbol.svg" alt="" aria-hidden="true" /><div><strong>GrowWise</strong><span>Personal Education OS</span></div></div>
        <button className="quiet-button" type="button" onClick={() => void refresh()}>새로고침</button>
      </header>

      <section className="hero"><p className="eyebrow">LOCAL-FIRST · PARENT-LED</p><h1>아이의 배움을 기록하고, 필요한 맥락을 연결합니다.</h1><p className="hero-copy">핵심 기록·검색·자료 관리는 AI 없이도 동작합니다. 로컬 모델은 정리와 검색, 생성을 선택적으로 보강합니다.</p></section>

      <section className="status-grid" aria-label="시스템 상태">
        <article className="status-card primary-card"><div className="card-heading"><span className={`status-dot ${isConnected ? "ok" : "warning"}`} /><h2>GrowWise Core</h2></div>{connection.kind === "loading" && <p>확인 중입니다.</p>}{connection.kind === "offline" && <p className="muted">{connection.message}</p>}{connection.kind === "connected" && <><p className="status-title">정상 연결</p><p className="muted">{connection.runtime.started_by_desktop ? "Desktop이 Core를 자동 기동했습니다." : "실행 중인 Core에 연결했습니다."}</p></>}</article>
        <article className="status-card"><p className="card-label">운영 모드</p><p className="status-title">{mode === "ai_enhanced_with_core_fallback" ? "AI 보강 + Core fallback" : mode === "core_only" ? "Core-only" : "확인 대기"}</p><p className="muted">LLM 장애가 핵심 기능 중단으로 이어지지 않습니다.</p></article>
        <article className="status-card"><p className="card-label">현재 아이</p><p className="status-title">{activeChild?.nickname ?? "선택 안 됨"}</p><p className="muted">저장된 아이 {children.length}명 · child scope를 엄격히 분리합니다.</p></article>
      </section>

      <section className="workspace">
        <div className="section-heading"><div><p className="eyebrow">CHILD CONTEXT</p><h2>기존 기록을 이어서 사용합니다.</h2></div><span className="badge">Pre-alpha</span></div>
        {children.length > 0 && <div className="child-switcher"><label><span>아이 선택</span><select value={activeChild?.id ?? ""} onChange={(event) => void handleSelectChild(event.target.value)}>{children.map((child) => <option key={child.id} value={child.id}>{child.nickname} · {child.age_months ?? "-"}개월</option>)}</select></label><p className="muted">마지막 선택을 기억하지만 데이터는 항상 Core에서 다시 조회합니다.</p></div>}

        <div className="skeleton-grid">
          <form className="profile-form" onSubmit={handleCreateChild}><p className="card-label">NEW CHILD</p><label><span>아이 닉네임</span><input value={nickname} onChange={(event) => setNickname(event.target.value)} placeholder="예: 아이" maxLength={40} disabled={!isConnected || saving} /></label><label><span>월령</span><input type="number" min="0" max="24" value={ageMonths} onChange={(event) => setAgeMonths(event.target.value)} disabled={!isConnected || saving} /></label><button className="primary-button" type="submit" disabled={!isConnected || saving}>{saving ? "저장 중…" : "새 프로필 저장"}</button>{formError && <p className="form-error">{formError}</p>}</form>
          <article className="verification-card">{activeChild && growthMap ? <><p className="card-label">ACTIVE CONTEXT</p><h3>{activeChild.nickname}</h3><p className="muted">프로필과 장기 기록은 Core 저장소에서 다시 불러왔습니다.</p><dl className="verification-list"><div><dt>월령</dt><dd>{activeChild.age_months ?? "-"}개월</dd></div><div><dt>최근 기록</dt><dd>{growthMap.total_logs_in_period}건</dd></div><div><dt>자료</dt><dd>{resources.length}건</dd></div></dl></> : <><p className="card-label">EMPTY</p><h3>아이 프로필을 만들어 주세요.</h3></>}</article>
        </div>

        {activeChild && <>
          <div className="observation-panel">
            <form className="observation-form" onSubmit={handleCreateObservation}><div><p className="card-label">OBSERVATION</p><h3>의미 있는 관찰만 기록합니다.</h3><p className="muted">축 선택은 선택 사항이며 AI 없이도 projection이 계산됩니다.</p></div><textarea value={observation} onChange={(event) => setObservation(event.target.value)} placeholder="예: 그림책의 고양이 그림을 오래 바라보고 여러 번 손으로 가리켰다." maxLength={10000} disabled={observationSaving} /><div className="axis-picker">{AXIS_OPTIONS.map((option) => { const active = selectedAxes.includes(option.value); return <button key={option.value} type="button" className={`axis-chip ${active ? "active" : ""}`} aria-pressed={active} onClick={() => toggleAxis(option.value)}>{option.label}</button>; })}</div><button className="primary-button" type="submit" disabled={observationSaving}>{observationSaving ? "기록 중…" : "관찰 저장"}</button>{observationError && <p className="form-error">{observationError}</p>}</form>
            <article className="observation-result"><p className="card-label">GROWTH CONTEXT</p><h3>최근 {growthMap?.period_days ?? 30}일</h3><p className="muted">기록 {growthMap?.total_logs_in_period ?? 0}건 · 경험 축 연결 {growthMap?.tagged_logs_in_period ?? 0}건</p><div className="axis-summary">{growthMap?.axes.filter((axis) => axis.observation_count > 0).map((axis) => <span key={axis.axis}>{AXIS_OPTIONS.find((item) => item.value === axis.axis)?.label ?? axis.axis} · {axis.observation_count}</span>)}</div></article>
          </div>

          <section className="search-section">
            <p className="card-label">NATURAL-LANGUAGE SEARCH</p><h3>기록을 자연어로 찾습니다.</h3><p className="muted">AI가 없어도 child-scoped lexical 검색이 작동합니다.</p>
            <form className="search-form" onSubmit={handleSearch}><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="예: 고양이 그림에 관심 보인 기록 찾아줘" /><button className="primary-button" type="submit" disabled={searching}>{searching ? "검색 중…" : "검색"}</button></form>{searchError && <p className="form-error">{searchError}</p>}
            {searchResult && <div className="search-results"><p className="muted">검색 키워드: {searchResult.plan.keywords.join(", ") || "원문 사용"} · 결과 {searchResult.results.length}건</p>{searchResult.results.map((result, index) => <article className="search-result-card" key={String(result.id ?? index)}><p>{resultText(result)}</p></article>)}</div>}
          </section>

          <section className="conversation-section">
            <p className="card-label">BOUNDED MULTI-TURN</p><h3>후속 질문으로 맥락을 좁힙니다.</h3><p className="muted">대화는 지시어 해석에만 쓰고, 사실 근거는 매 턴 원본 기록과 Resource KB에서 다시 찾습니다.</p>
            <form className="search-form" onSubmit={handleConversation}><input value={conversationQuestion} onChange={(event) => setConversationQuestion(event.target.value)} placeholder="예: 그중 고양이 관련 기록만 보여줘" /><button className="primary-button" type="submit" disabled={conversationBusy}>{conversationBusy ? "확인 중…" : conversation ? "후속 질문" : "세션 시작"}</button></form>{conversationError && <p className="form-error">{conversationError}</p>}
            {conversation && <p className="muted session-meta">session {conversation.id.slice(0, 8)}… · child scope 고정</p>}
            <div className="conversation-list">{conversationAnswers.map((item, index) => <article className="conversation-card" key={`${item.session_id}-${index}`}><p>{item.answer.answer}</p><small>{item.answer.source_ids.length > 0 ? `근거 ${item.answer.source_ids.length}건 · ${item.answer.source_ids.join(", ")}` : item.answer.insufficient_evidence ? "근거 부족" : "근거 없음"}</small></article>)}</div>
          </section>

          <section className="resource-section">
            <div className="resource-grid"><form className="resource-form" onSubmit={handleCreateResource}><p className="card-label">RESOURCE LIBRARY</p><h3>자료를 지식베이스에 넣습니다.</h3><label><span>종류</span><select value={resourceKind} onChange={(event) => setResourceKind(event.target.value as ResourceKind)}><option value="note">메모</option><option value="book">도서</option><option value="curriculum">교육과정</option><option value="web">웹 자료</option><option value="file">파일 메모</option></select></label><label><span>제목</span><input value={resourceTitle} onChange={(event) => setResourceTitle(event.target.value)} maxLength={500} /></label><label><span>내용</span><textarea value={resourceContent} onChange={(event) => setResourceContent(event.target.value)} placeholder="자료의 핵심 내용이나 메모" /></label><button className="primary-button" type="submit" disabled={resourceSaving}>{resourceSaving ? "저장 중…" : "자료 저장"}</button>{resourceError && <p className="form-error">{resourceError}</p>}</form><div className="resource-list"><p className="card-label">INDEXED RESOURCES</p><h3>{resources.length}건</h3>{resources.length === 0 ? <p className="muted">아직 이 아이와 연결된 자료가 없습니다.</p> : resources.map((resource) => <article className="resource-card" key={resource.id}><strong>{resource.title}</strong><span>{resource.kind}</span>{resource.content && <p>{resource.content}</p>}</article>)}</div></div>
          </section>

          <section className="timeline-section"><div className="activity-heading"><div><p className="card-label">OBSERVATION TIMELINE</p><h3>관찰 기록</h3></div><span className="badge">{timeline.length}건</span></div>{timeline.length === 0 ? <p className="muted">아직 기록이 없습니다. 기록 공백은 실패가 아닙니다.</p> : <div className="timeline-list">{timeline.map((log) => <article key={log.id} className="timeline-card"><p>{log.parent_observation}</p><div className="axis-summary">{log.experience_axes.map((axis) => <span key={axis}>{AXIS_OPTIONS.find((item) => item.value === axis)?.label ?? axis}</span>)}</div>{log.created_at && <time dateTime={log.created_at}>{new Date(log.created_at).toLocaleString("ko-KR")}</time>}</article>)}</div>}</section>

          <section className="activity-section"><div className="activity-heading"><div><p className="card-label">ACTIVITY INVITATIONS</p><h3>다음 활동 후보</h3><p className="muted">AI가 가능하면 최근 맥락을 반영하고, 아니면 deterministic fallback을 사용합니다.</p></div><button className="quiet-button" type="button" onClick={() => void handleLoadActivities()} disabled={activitiesLoading}>{activitiesLoading ? "불러오는 중…" : "활동 후보 보기"}</button></div>{activitiesError && <p className="form-error">{activitiesError}</p>}{activities && <div className="activity-grid">{activities.suggestions.map((suggestion) => <article className="activity-card" key={`${suggestion.title}-${suggestion.description}`}><h4>{suggestion.title}</h4><p>{suggestion.description}</p>{suggestion.observation_cue && <small>{suggestion.observation_cue}</small>}</article>)}</div>}</section>
        </>}
      </section>
    </main>
  );
}

export default App;
