import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { readRememberedChildId, useActiveChild } from "./active-child-context";
import {
  ConfirmDialog,
  MaterialWorkspaceIntegration,
  OperationNotice,
  ViewStateNotice,
} from "./components";
import {
  ActivitiesSection,
  ChildProfileSection,
  DataManagementSection,
  InfantGuidanceSection,
  ObservationGrowthSection,
  ObservationTimelineSection,
  ResourceLibrarySection,
  SearchConversationSection,
  SystemStatusSection,
} from "./features";
import {
  childContextState,
  errorMessage,
  isCurrentChildScope,
  type ChildContextKey,
  type ChildContextLoadState,
  type ViewLoadState,
} from "./child-context-state";
import { activityStatusLabel } from "./presentation";
import { useBackupManagement } from "./use-backup-management";
import { useMaterialManagement } from "./use-material-management";
import {
  appendConversationTurn,
  createActivity,
  createChild,
  createConversation,
  createObservation,
  createResource,
  deleteResource,
  getBoardBookRecommendations,
  getCoreRuntimeStatus,
  getGrowthMap,
  getHealth,
  getInfantActivities,
  getInfantObservationHints,
  listActivities,
  listChildren,
  listMaterials,
  listObservations,
  listResources,
  searchChildContext,
  transitionActivity,
  updateResource,
  type ActivityPlan,
  type ActivityStatus,
  type BoardBookRecommendations,
  type ChildProfile,
  type ConversationAnswer,
  type ConversationSession,
  type CoreRuntimeStatus,
  type ExperienceAxis,
  type GeneratedMaterial,
  type GrowthMap,
  type HealthResponse,
  type InfantActivitySuggestions,
  type InfantObservationHints,
  type LearningLog,
  type ResourceCreateInput,
  type ResourceKind,
  type ResourceRecord,
  type SearchResponse,
  type Stage,
} from "./api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse; runtime: CoreRuntimeStatus }
  | { kind: "offline"; message: string };

type WriteNotice = { id: number; message: string };

function App() {
  const {
    selectChild: selectSharedChild,
    upsertChild: upsertSharedChild,
  } = useActiveChild();
  const {
    backups,
    backupBusy,
    backupError,
    backupNotice,
    backupConfirmation,
    backupConfirmationTitle,
    backupConfirmationDescription,
    backupConfirmationLabel,
    refreshBackups,
    handleCreateBackup,
    handleExportBackup,
    handleImportBackup,
    handleRestoreBackup,
    confirmBackupAction,
    handleCancelBackupAction,
  } = useBackupManagement();
  const [connection, setConnection] = useState<ConnectionState>({ kind: "loading" });
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [activeChild, setActiveChild] = useState<ChildProfile | null>(null);
  const [growthMap, setGrowthMap] = useState<GrowthMap | null>(null);
  const [timeline, setTimeline] = useState<LearningLog[]>([]);
  const [resources, setResources] = useState<ResourceRecord[]>([]);
  const [materials, setMaterials] = useState<GeneratedMaterial[]>([]);
  const [activityPlans, setActivityPlans] = useState<ActivityPlan[]>([]);
  const [childContext, setChildContext] = useState<ChildContextLoadState>(() =>
    childContextState("idle"),
  );
  const childContextRequestId = useRef(0);
  const activeChildIdRef = useRef<string | null>(null);

  const [nickname, setNickname] = useState("");
  const [childStage, setChildStage] = useState<Stage>("infant_0_2");
  const [ageMonths, setAgeMonths] = useState("9");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [observation, setObservation] = useState("");
  const [selectedAxes, setSelectedAxes] = useState<ExperienceAxis[]>([]);
  const [selectedActivityId, setSelectedActivityId] = useState("");
  const [observationSaving, setObservationSaving] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [activities, setActivities] = useState<InfantActivitySuggestions | null>(null);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);
  const [activityPlanBusy, setActivityPlanBusy] = useState(false);
  const [observationHints, setObservationHints] = useState<InfantObservationHints | null>(null);
  const [boardBooks, setBoardBooks] = useState<BoardBookRecommendations | null>(null);
  const [infantGuidanceLoading, setInfantGuidanceLoading] = useState(false);
  const [infantGuidanceError, setInfantGuidanceError] = useState<string | null>(null);

  const [conversation, setConversation] = useState<ConversationSession | null>(null);
  const [conversationAnswers, setConversationAnswers] = useState<ConversationAnswer[]>([]);
  const [conversationQuestion, setConversationQuestion] = useState("");
  const [conversationBusy, setConversationBusy] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);

  const [resourceKind, setResourceKind] = useState<ResourceKind>("note");
  const [resourceTitle, setResourceTitle] = useState("");
  const [resourceContent, setResourceContent] = useState("");
  const [resourceSaving, setResourceSaving] = useState(false);
  const [resourceError, setResourceError] = useState<string | null>(null);


  const [printMaterial, setPrintMaterial] = useState<GeneratedMaterial | null>(null);
  const [writeNotice, setWriteNotice] = useState<WriteNotice | null>(null);
  const writeNoticeId = useRef(0);

  const updateChildContextState = useCallback((key: ChildContextKey, state: ViewLoadState) => {
    setChildContext((current) => ({ ...current, [key]: state }));
  }, []);

  const scopeIsCurrent = useCallback((childId: string, requestId: number) => {
    return isCurrentChildScope(
      childId,
      requestId,
      activeChildIdRef.current,
      childContextRequestId.current,
    );
  }, []);

  const {
    materialKind,
    materialTopic,
    materialGoal,
    selectedResourceRefs,
    materialBusy,
    materialError,
    revisionNotes,
    editingMaterialId,
    setMaterialKind,
    setMaterialTopic,
    setMaterialGoal,
    toggleResourceRef,
    removeResourceRef,
    setRevisionNote,
    setEditingMaterialId,
    handleGenerateMaterial,
    handleReviewMaterial,
    handleReviseMaterial,
    handleParentEdit,
    resetMaterialState,
  } = useMaterialManagement({
    childId: activeChild?.id ?? null,
    getRequestId: () => childContextRequestId.current,
    scopeIsCurrent,
    reloadMaterials: () => reloadChildContextPart("materials"),
    announceWrite,
  });

  const loadChildContext = useCallback(
    async (child: ChildProfile) => {
      const requestId = ++childContextRequestId.current;
      activeChildIdRef.current = child.id;
      selectSharedChild(child.id);
      setActiveChild(child);
      setGrowthMap(null);
      setTimeline([]);
      setResources([]);
      setMaterials([]);
      setActivityPlans([]);
      setChildContext(childContextState("loading"));
      setObservation("");
      setSelectedAxes([]);
      setSelectedActivityId("");
      setActivities(null);
      setActivitiesLoading(false);
      setActivitiesError(null);
      setActivityPlanBusy(false);
      setObservationHints(null);
      setBoardBooks(null);
      setInfantGuidanceLoading(false);
      setInfantGuidanceError(null);
      setSearchQuery("");
      setSearchResult(null);
      setSearching(false);
      setSearchError(null);
      setConversation(null);
      setConversationAnswers([]);
      setConversationQuestion("");
      setConversationBusy(false);
      setConversationError(null);
      setResourceTitle("");
      setResourceContent("");
      setResourceSaving(false);
      setResourceError(null);
      resetMaterialState();

      const [growthResult, observationsResult, resourcesResult, materialsResult, activitiesResult] =
        await Promise.allSettled([
          getGrowthMap(child.id),
          listObservations(child.id),
          listResources(child.id),
          listMaterials(child.id),
          listActivities(child.id),
        ]);

      if (!scopeIsCurrent(child.id, requestId)) return;

      if (growthResult.status === "fulfilled") setGrowthMap(growthResult.value);
      if (observationsResult.status === "fulfilled") setTimeline(observationsResult.value);
      if (resourcesResult.status === "fulfilled") setResources(resourcesResult.value);
      if (materialsResult.status === "fulfilled") setMaterials(materialsResult.value);
      if (activitiesResult.status === "fulfilled") setActivityPlans(activitiesResult.value);

      setChildContext({
        growth:
          growthResult.status === "fulfilled"
            ? { kind: "ready" }
            : {
                kind: "error",
                message: errorMessage(growthResult.reason, "성장 맥락을 불러오지 못했습니다."),
              },
        observations:
          observationsResult.status === "fulfilled"
            ? { kind: "ready" }
            : {
                kind: "error",
                message: errorMessage(observationsResult.reason, "관찰 기록을 불러오지 못했습니다."),
              },
        library:
          resourcesResult.status === "fulfilled"
            ? { kind: "ready" }
            : {
                kind: "error",
                message: errorMessage(resourcesResult.reason, "자료 목록을 불러오지 못했습니다."),
              },
        materials:
          materialsResult.status === "fulfilled"
            ? { kind: "ready" }
            : {
                kind: "error",
                message: errorMessage(materialsResult.reason, "생성 자료를 불러오지 못했습니다."),
              },
        activities:
          activitiesResult.status === "fulfilled"
            ? { kind: "ready" }
            : {
                kind: "error",
                message: errorMessage(activitiesResult.reason, "활동 목록을 불러오지 못했습니다."),
              },
      });
    },
    [resetMaterialState, scopeIsCurrent, selectSharedChild],
  );

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

      await refreshBackups();

      if (storedChildren.length > 0) {
        const rememberedId = readRememberedChildId(window.localStorage);
        const selected =
          storedChildren.find((child) => child.id === rememberedId) ?? storedChildren[0];
        await loadChildContext(selected);
      } else {
        childContextRequestId.current += 1;
        activeChildIdRef.current = null;
        selectSharedChild("");
        setActiveChild(null);
        setGrowthMap(null);
        setTimeline([]);
        setResources([]);
        setMaterials([]);
        setActivityPlans([]);
        setChildContext(childContextState("idle"));
        setSelectedActivityId("");
      }
    } catch (error) {
      childContextRequestId.current += 1;
      activeChildIdRef.current = null;
      setConnection({
        kind: "offline",
        message: errorMessage(error, "GrowWise Core 상태를 확인할 수 없습니다."),
      });
    }
  }, [loadChildContext, refreshBackups, selectSharedChild]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!writeNotice) return;
    const noticeId = writeNotice.id;
    const timeoutId = window.setTimeout(() => {
      setWriteNotice((current) => (current?.id === noticeId ? null : current));
    }, 4500);
    return () => window.clearTimeout(timeoutId);
  }, [writeNotice]);

  function announceWrite(message: string) {
    writeNoticeId.current += 1;
    setWriteNotice({ id: writeNoticeId.current, message });
  }

  async function reloadChildContextPart(key: ChildContextKey) {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    if (!scopeIsCurrent(childId, requestId)) return;
    updateChildContextState(key, { kind: "loading" });

    try {
      if (key === "growth") {
        const value = await getGrowthMap(childId);
        if (!scopeIsCurrent(childId, requestId)) return;
        setGrowthMap(value);
      } else if (key === "observations") {
        const value = await listObservations(childId);
        if (!scopeIsCurrent(childId, requestId)) return;
        setTimeline(value);
      } else if (key === "library") {
        const value = await listResources(childId);
        if (!scopeIsCurrent(childId, requestId)) return;
        setResources(value);
      } else if (key === "materials") {
        const value = await listMaterials(childId);
        if (!scopeIsCurrent(childId, requestId)) return;
        setMaterials(value);
      } else {
        const value = await listActivities(childId);
        if (!scopeIsCurrent(childId, requestId)) return;
        setActivityPlans(value);
      }
      if (scopeIsCurrent(childId, requestId)) {
        updateChildContextState(key, { kind: "ready" });
      }
    } catch (error) {
      if (!scopeIsCurrent(childId, requestId)) return;
      const fallback = {
        growth: "성장 맥락을 불러오지 못했습니다.",
        observations: "관찰 기록을 불러오지 못했습니다.",
        library: "자료 목록을 불러오지 못했습니다.",
        materials: "생성 자료를 불러오지 못했습니다.",
        activities: "활동 목록을 불러오지 못했습니다.",
      }[key];
      updateChildContextState(key, { kind: "error", message: errorMessage(error, fallback) });
    }
  }

  async function handleCreateChild(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedNickname = nickname.trim();
    const trimmedAge = ageMonths.trim();
    const parsedAge = trimmedAge ? Number.parseInt(trimmedAge, 10) : null;
    if (!trimmedNickname) return setFormError("아이를 구분할 닉네임을 입력해 주세요.");
    if (parsedAge !== null && (!Number.isFinite(parsedAge) || parsedAge < 0 || parsedAge > 240)) {
      return setFormError("월령은 비워 두거나 0~240개월로 입력해 주세요.");
    }
    setSaving(true);
    setFormError(null);
    try {
      const child = await createChild({
        nickname: trimmedNickname,
        stage: childStage,
        age_months: parsedAge,
        interests: [],
      });
      upsertSharedChild(child, { select: true });
      setChildren((current) => [child, ...current.filter((item) => item.id !== child.id)]);
      await loadChildContext(child);
      setNickname("");
      setAgeMonths("");
      announceWrite("아이 프로필을 저장했습니다.");
    } catch (error) {
      setFormError(errorMessage(error, "프로필 저장에 실패했습니다."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSelectChild(childId: string) {
    const child = children.find((item) => item.id === childId);
    if (!child) return;
    setFormError(null);
    try {
      await loadChildContext(child);
    } catch (error) {
      setFormError(errorMessage(error, "아이 정보를 불러오지 못했습니다."));
    }
  }

  async function handleCreateObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    const text = observation.trim();
    if (!text) return setObservationError("기억할 가치가 있는 관찰을 짧게 적어 주세요.");
    setObservationSaving(true);
    setObservationError(null);
    try {
      await createObservation({
        child_id: childId,
        observation: text,
        experience_axes: selectedAxes,
        activity_plan_id: selectedActivityId || null,
      });
      if (!scopeIsCurrent(childId, requestId)) return;
      setObservation("");
      setSelectedAxes([]);
      setSelectedActivityId("");
      setActivities(null);
      setSearchResult(null);
      await Promise.all([
        reloadChildContextPart("growth"),
        reloadChildContextPart("observations"),
      ]);
      if (scopeIsCurrent(childId, requestId)) announceWrite("관찰 기록을 저장했습니다.");
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setObservationError(errorMessage(error, "관찰 기록 저장에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setObservationSaving(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    const query = searchQuery.trim();
    if (query.length < 2) return setSearchError("두 글자 이상으로 검색해 주세요.");
    setSearching(true);
    setSearchError(null);
    try {
      const result = await searchChildContext(childId, query);
      if (!scopeIsCurrent(childId, requestId)) return;
      setSearchResult(result);
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setSearchError(errorMessage(error, "검색에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setSearching(false);
    }
  }

  async function handleConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    const question = conversationQuestion.trim();
    if (question.length < 2) return setConversationError("두 글자 이상으로 질문해 주세요.");
    setConversationBusy(true);
    setConversationError(null);
    try {
      const session = conversation ?? (await createConversation(childId));
      const answer = await appendConversationTurn(session.id, question);
      if (!scopeIsCurrent(childId, requestId)) return;
      setConversation(session);
      setConversationAnswers((current) => [...current, answer]);
      setConversationQuestion("");
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setConversationError(errorMessage(error, "후속 질문 처리에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setConversationBusy(false);
    }
  }

  async function handleCreateResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    const title = resourceTitle.trim();
    const content = resourceContent.trim();
    if (!title) return setResourceError("자료 제목을 입력해 주세요.");
    setResourceSaving(true);
    setResourceError(null);
    try {
      await createResource({
        kind: resourceKind,
        title,
        child_id: childId,
        summary: null,
        content: content || null,
        source_url: null,
        source_name: "parent",
        author: null,
        tags: [],
        stage_tags: [activeChild.stage],
        provenance: { origin: "desktop_manual" },
      });
      if (!scopeIsCurrent(childId, requestId)) return;
      setResourceTitle("");
      setResourceContent("");
      await reloadChildContextPart("library");
      if (scopeIsCurrent(childId, requestId)) announceWrite("자료를 저장했습니다.");
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setResourceError(errorMessage(error, "자료 저장에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setResourceSaving(false);
    }
  }

  async function handleUpdateResource(resourceId: string, request: ResourceCreateInput) {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    setResourceSaving(true);
    setResourceError(null);
    try {
      const updated = await updateResource(resourceId, request, childId);
      if (!scopeIsCurrent(childId, requestId)) return;
      setResources((current) =>
        current.map((resource) => (resource.id === updated.id ? updated : resource)),
      );
      announceWrite("자료를 수정했습니다.");
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setResourceError(errorMessage(error, "자료 수정에 실패했습니다."));
      }
      throw error;
    } finally {
      if (scopeIsCurrent(childId, requestId)) setResourceSaving(false);
    }
  }

  async function handleDeleteResource(resourceId: string) {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    setResourceSaving(true);
    setResourceError(null);
    try {
      await deleteResource(resourceId, childId);
      if (!scopeIsCurrent(childId, requestId)) return;
      setResources((current) => current.filter((resource) => resource.id !== resourceId));
      removeResourceRef(resourceId);
      announceWrite("자료를 삭제했습니다.");
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setResourceError(errorMessage(error, "자료 삭제에 실패했습니다."));
      }
      throw error;
    } finally {
      if (scopeIsCurrent(childId, requestId)) setResourceSaving(false);
    }
  }

  async function handleLoadActivities() {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    setActivitiesLoading(true);
    setActivitiesError(null);
    try {
      const result = await getInfantActivities(childId);
      if (!scopeIsCurrent(childId, requestId)) return;
      setActivities(result);
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setActivitiesError(errorMessage(error, "활동 후보를 불러오지 못했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setActivitiesLoading(false);
    }
  }

  async function handleLoadInfantGuidance() {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    setInfantGuidanceLoading(true);
    setInfantGuidanceError(null);
    try {
      const [hints, books] = await Promise.all([
        getInfantObservationHints(childId),
        getBoardBookRecommendations(childId),
      ]);
      if (!scopeIsCurrent(childId, requestId)) return;
      setObservationHints(hints);
      setBoardBooks(books);
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setInfantGuidanceError(errorMessage(error, "영아 관찰 가이드를 불러오지 못했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setInfantGuidanceLoading(false);
    }
  }

  async function handleSaveActivity(title: string) {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    setActivityPlanBusy(true);
    setActivitiesError(null);
    try {
      await createActivity(childId, title);
      if (!scopeIsCurrent(childId, requestId)) return;
      await reloadChildContextPart("activities");
      if (scopeIsCurrent(childId, requestId)) announceWrite("활동으로 저장했습니다.");
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setActivitiesError(errorMessage(error, "활동 저장에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setActivityPlanBusy(false);
    }
  }

  async function handleActivityTransition(activityId: string, status: ActivityStatus) {
    if (!activeChild) return;
    const childId = activeChild.id;
    const requestId = childContextRequestId.current;
    setActivityPlanBusy(true);
    setActivitiesError(null);
    try {
      await transitionActivity(activityId, status);
      if (!scopeIsCurrent(childId, requestId)) return;
      await reloadChildContextPart("activities");
      if (scopeIsCurrent(childId, requestId)) {
        announceWrite(`활동 상태를 '${activityStatusLabel(status)}'으로 변경했습니다.`);
      }
    } catch (error) {
      if (scopeIsCurrent(childId, requestId)) {
        setActivitiesError(errorMessage(error, "활동 상태 변경에 실패했습니다."));
      }
    } finally {
      if (scopeIsCurrent(childId, requestId)) setActivityPlanBusy(false);
    }
  }

  async function handleConfirmBackupAction() {
    if (await confirmBackupAction()) {
      await refresh();
    }
  }

  function handlePrintMaterial(material: GeneratedMaterial) {
    if (material.status !== "approved") return;
    setPrintMaterial(material);
    window.setTimeout(() => window.print(), 0);
  }

  function toggleAxis(axis: ExperienceAxis) {
    setSelectedAxes((current) =>
      current.includes(axis) ? current.filter((item) => item !== axis) : [...current, axis],
    );
  }

  const isConnected = connection.kind === "connected";
  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <img className="brand-logo" src="/growwise-symbol.svg" alt="" aria-hidden="true" />
          <div><strong>GrowWise</strong><span>아이의 배움 기록</span></div>
        </div>
        <button className="quiet-button" type="button" onClick={() => void refresh()}>새로고침</button>
      </header>

      <section className="hero">
        <p className="eyebrow">기록 · 연결 · 활용</p>
        <h1>아이의 배움을 기록하고, 필요한 맥락을 연결합니다.</h1>
        <p className="hero-copy">기록·검색·자료 관리는 기본 기능으로 사용할 수 있으며, AI 보조 기능은 필요한 경우에만 사용할 수 있습니다.</p>
      </section>

      <SystemStatusSection connection={connection} activeChild={activeChild} childrenCount={children.length} />

      <section className="workspace">
        <ChildProfileSection
          connected={isConnected}
          children={children}
          activeChild={activeChild}
          childContext={childContext}
          growthMap={growthMap}
          activityCount={activityPlans.length}
          nickname={nickname}
          childStage={childStage}
          ageMonths={ageMonths}
          saving={saving}
          error={formError}
          onNicknameChange={setNickname}
          onStageChange={setChildStage}
          onAgeMonthsChange={setAgeMonths}
          onSubmit={handleCreateChild}
          onSelectChild={(childId) => void handleSelectChild(childId)}
        />

        {activeChild && (
          <>
            <ObservationGrowthSection
              observation={observation}
              selectedAxes={selectedAxes}
              selectedActivityId={selectedActivityId}
              saving={observationSaving}
              error={observationError}
              activityPlans={activityPlans}
              growthState={childContext.growth}
              growthMap={growthMap}
              onObservationChange={setObservation}
              onSelectedActivityChange={setSelectedActivityId}
              onToggleAxis={toggleAxis}
              onSubmit={handleCreateObservation}
              onRetryGrowth={() => void reloadChildContextPart("growth")}
            />

            <SearchConversationSection
              searchQuery={searchQuery}
              searchResult={searchResult}
              searching={searching}
              searchError={searchError}
              conversation={conversation}
              conversationAnswers={conversationAnswers}
              conversationQuestion={conversationQuestion}
              conversationBusy={conversationBusy}
              conversationError={conversationError}
              onSearchQueryChange={setSearchQuery}
              onSearch={handleSearch}
              onConversationQuestionChange={setConversationQuestion}
              onConversation={handleConversation}
            />

            <ResourceLibrarySection
              resourceKind={resourceKind}
              resourceTitle={resourceTitle}
              resourceContent={resourceContent}
              saving={resourceSaving}
              error={resourceError}
              loadState={childContext.library}
              resources={resources}
              onKindChange={setResourceKind}
              onTitleChange={setResourceTitle}
              onContentChange={setResourceContent}
              onSubmit={handleCreateResource}
              onRetry={() => void reloadChildContextPart("library")}
              onUpdate={handleUpdateResource}
              onDelete={handleDeleteResource}
            />

            {childContext.materials.kind === "loading" ? (
              <section className="material-workspace material-state-panel">
                <ViewStateNotice kind="loading" title="생성 자료를 불러오는 중입니다." description="다른 작업공간은 계속 사용할 수 있습니다." />
              </section>
            ) : childContext.materials.kind === "error" ? (
              <section className="material-workspace material-state-panel">
                <ViewStateNotice
                  kind="error"
                  title="생성 자료를 불러오지 못했습니다."
                  description={childContext.materials.message}
                  action={<button className="quiet-button" type="button" onClick={() => void reloadChildContextPart("materials")}>다시 시도</button>}
                />
              </section>
            ) : (
              <MaterialWorkspaceIntegration
                controller={{
                  materials,
                  resources,
                  stage: activeChild.stage,
                  materialKind,
                  materialTopic,
                  materialGoal,
                  selectedResourceRefs,
                  materialBusy,
                  materialError,
                  revisionNotes,
                  editingMaterialId,
                  setMaterialKind,
                  setMaterialTopic,
                  setMaterialGoal,
                  toggleResourceRef,
                  handleGenerateMaterial,
                  handleReviewMaterial,
                  setRevisionNote,
                  handleReviseMaterial,
                  setEditingMaterialId,
                  handleParentEdit,
                  handlePrintMaterial,
                }}
              />
            )}

            {activeChild.stage === "infant_0_2" && (
              <InfantGuidanceSection
                observationHints={observationHints}
                boardBooks={boardBooks}
                loading={infantGuidanceLoading}
                error={infantGuidanceError}
                onLoad={() => void handleLoadInfantGuidance()}
              />
            )}

            <ActivitiesSection
              suggestions={activities}
              suggestionsLoading={activitiesLoading}
              error={activitiesError}
              planBusy={activityPlanBusy}
              plans={activityPlans}
              loadState={childContext.activities}
              onLoadSuggestions={() => void handleLoadActivities()}
              onSaveActivity={(title) => void handleSaveActivity(title)}
              onTransition={(activityId, status) => void handleActivityTransition(activityId, status)}
              onRetryPlans={() => void reloadChildContextPart("activities")}
            />

            <ObservationTimelineSection
              loadState={childContext.observations}
              timeline={timeline}
              activityPlans={activityPlans}
              onRetry={() => void reloadChildContextPart("observations")}
            />
          </>
        )}
      </section>

      <DataManagementSection
        connected={isConnected}
        backups={backups}
        busy={backupBusy}
        error={backupError}
        notice={backupNotice}
        onImport={handleImportBackup}
        onCreate={() => void handleCreateBackup()}
        onExport={(archiveName) => void handleExportBackup(archiveName)}
        onRestore={handleRestoreBackup}
      />

      <ConfirmDialog
        open={backupConfirmation !== null}
        title={backupConfirmationTitle}
        description={backupConfirmationDescription}
        confirmLabel={backupConfirmationLabel}
        busy={backupBusy}
        destructive
        onConfirm={() => void handleConfirmBackupAction()}
        onCancel={handleCancelBackupAction}
      />
      <OperationNotice message={writeNotice?.message ?? null} onDismiss={() => setWriteNotice(null)} />

      {printMaterial && (
        <article className="print-material" aria-hidden="true">
          <h1>{printMaterial.title}</h1>
          <pre>{printMaterial.content_markdown}</pre>
        </article>
      )}
    </main>
  );
}

export default App;