import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { readRememberedChildId, useActiveChild } from "./active-child-context";
import {
  ConfirmDialog,
  MaterialWorkspaceIntegration,
  OperationNotice,
  ViewStateNotice,
  type WorkspaceViewName,
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
import { stageForBirthDate } from "./child-stage";
import { activityStatusLabel } from "./presentation";
import { useBackupManagement } from "./use-backup-management";
import { useMaterialManagement } from "./use-material-management";
import { useResourceManagement } from "./use-resource-management";
import { useSearchConversation } from "./use-search-conversation";
import {
  createActivity,
  createChild,
  createObservation,
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
  transitionActivity,
  type ActivityPlan,
  type ActivityStatus,
  type BoardBookRecommendations,
  type ChildProfile,
  type CoreRuntimeStatus,
  type ExperienceAxis,
  type GeneratedMaterial,
  type GrowthMap,
  type HealthResponse,
  type InfantActivitySuggestions,
  type InfantObservationHints,
  type LearningLog,
  type ResourceRecord,
  type Stage,
} from "./api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse; runtime: CoreRuntimeStatus }
  | { kind: "offline"; message: string };

type WriteNotice = { id: number; message: string };

function App({
  activeView,
  onNavigate,
}: {
  activeView: WorkspaceViewName;
  onNavigate?: (view: WorkspaceViewName) => void;
}) {
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
  const [birthDate, setBirthDate] = useState("");
  const [ageMonths, setAgeMonths] = useState("");
  const [grade, setGrade] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function handleBirthDateChange(value: string) {
    setBirthDate(value);
    const derivedStage = stageForBirthDate(value);
    if (derivedStage) setChildStage(derivedStage);
    if (value) {
      setAgeMonths("");
      setGrade("");
    }
  }

  const [observation, setObservation] = useState("");
  const [selectedAxes, setSelectedAxes] = useState<ExperienceAxis[]>([]);
  const [selectedActivityId, setSelectedActivityId] = useState("");
  const [observationSaving, setObservationSaving] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);


  const [activities, setActivities] = useState<InfantActivitySuggestions | null>(null);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [activitiesError, setActivitiesError] = useState<string | null>(null);
  const [activityPlanBusy, setActivityPlanBusy] = useState(false);
  const [observationHints, setObservationHints] = useState<InfantObservationHints | null>(null);
  const [boardBooks, setBoardBooks] = useState<BoardBookRecommendations | null>(null);
  const [infantGuidanceLoading, setInfantGuidanceLoading] = useState(false);
  const [infantGuidanceError, setInfantGuidanceError] = useState<string | null>(null);




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
    handleUseMaterial,
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

  const {
    resourceKind,
    resourceTitle,
    resourceContent,
    resourceSaving,
    resourceError,
    setResourceKind,
    setResourceTitle,
    setResourceContent,
    handleCreateResource,
    handleUpdateResource,
    handleDeleteResource,
    resetResourceState,
  } = useResourceManagement({
    child: activeChild,
    getRequestId: () => childContextRequestId.current,
    scopeIsCurrent,
    reloadLibrary: () => reloadChildContextPart("library"),
    replaceResource: (updated) =>
      setResources((current) =>
        current.map((resource) => (resource.id === updated.id ? updated : resource)),
      ),
    removeResource: (resourceId) =>
      setResources((current) => current.filter((resource) => resource.id !== resourceId)),
    removeResourceRef,
    announceWrite,
  });

  const {
    searchQuery,
    searchResult,
    searching,
    searchError,
    conversation,
    conversationAnswers,
    conversationQuestion,
    conversationBusy,
    conversationError,
    setSearchQuery,
    setConversationQuestion,
    handleSearch,
    handleConversation,
    selectConversation,
    clearSearchResult,
    resetSearchConversation,
  } = useSearchConversation({
    childId: activeChild?.id ?? null,
    getRequestId: () => childContextRequestId.current,
    scopeIsCurrent,
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
      resetMaterialState();
      resetResourceState();
      resetSearchConversation();

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
    [resetMaterialState, resetResourceState, resetSearchConversation, scopeIsCurrent, selectSharedChild],
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
    const trimmedGrade = grade.trim();
    const parsedAge = trimmedAge ? Number.parseInt(trimmedAge, 10) : null;
    const parsedGrade = trimmedGrade ? Number.parseInt(trimmedGrade, 10) : null;
    const firstProfile = children.length === 0;
    if (!trimmedNickname) return setFormError("아이를 구분할 닉네임을 입력해 주세요.");
    if (birthDate && Number.isNaN(Date.parse(`${birthDate}T00:00:00`))) {
      return setFormError("생년월일을 확인해 주세요.");
    }
    if (parsedAge !== null && (!Number.isFinite(parsedAge) || parsedAge < 0 || parsedAge > 240)) {
      return setFormError("월령은 비워 두거나 0~240개월로 입력해 주세요.");
    }
    if (
      parsedGrade !== null
      && (!Number.isInteger(parsedGrade) || parsedGrade < 1 || parsedGrade > 12)
    ) {
      return setFormError("학년은 비워 두거나 1~12 사이로 입력해 주세요.");
    }
    setSaving(true);
    setFormError(null);
    try {
      const child = await createChild({
        nickname: trimmedNickname,
        stage: childStage,
        birth_date: birthDate || null,
        age_months: birthDate ? null : parsedAge,
        grade: birthDate ? null : parsedGrade,
        interests: [],
      });
      upsertSharedChild(child, { select: true });
      setChildren((current) => [child, ...current.filter((item) => item.id !== child.id)]);
      await loadChildContext(child);
      setNickname("");
      setBirthDate("");
      setAgeMonths("");
      setGrade("");
      announceWrite(
        firstProfile
          ? "첫 프로필을 저장했습니다. 바로 첫 활동을 만들어 보세요."
          : "아이 프로필을 저장했습니다.",
      );
      if (firstProfile) onNavigate?.("materials");
    } catch (error) {
      setFormError(errorMessage(error, "프로필 저장에 실패했습니다."));
    } finally {
      setSaving(false);
    }
  }

  function handleAvatarUpdated(child: ChildProfile) {
    upsertSharedChild(child, { select: true });
    setChildren((current) => current.map((item) => (item.id === child.id ? child : item)));
    if (activeChildIdRef.current === child.id) setActiveChild(child);
  }

  async function handleManagedProfileUpdated(child: ChildProfile) {
    upsertSharedChild(child, { select: activeChildIdRef.current === child.id });
    setChildren((current) =>
      current.map((item) => (item.id === child.id ? child : item)),
    );
    if (activeChildIdRef.current === child.id) {
      await loadChildContext(child);
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
      clearSearchResult();
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

  async function handleMaterialResultRecorded() {
    await Promise.all([
      reloadChildContextPart("activities"),
      reloadChildContextPart("observations"),
      reloadChildContextPart("growth"),
    ]);
  }

  function toggleAxis(axis: ExperienceAxis) {
    setSelectedAxes((current) =>
      current.includes(axis) ? current.filter((item) => item !== axis) : [...current, axis],
    );
  }

  const isConnected = connection.kind === "connected";
  const showProfile = activeView === "profile";
  const showObservation =
    activeView === "profile"
    || activeView === "learning"
    || activeView === "observations"
    || activeView === "growth";
  const showConversation = activeView === "conversation" || activeView === "search";
  const showLibrary = activeView === "materials" || activeView === "library";
  const showMaterials = activeView === "materials";
  const showActivities = activeView === "materials" || activeView === "activities";
  const showTimeline =
    activeView === "profile" || activeView === "learning" || activeView === "observations";
  const showChildWorkspace =
    showProfile
    || showObservation
    || showConversation
    || showLibrary
    || showMaterials
    || showActivities
    || showTimeline;

  return (
    <div className="app-shell">
      {showChildWorkspace && (
        <section className="workspace">
          {showProfile && (
            <ChildProfileSection
              connected={isConnected}
              children={children}
              activeChild={activeChild}
              childContext={childContext}
              growthMap={growthMap}
              activityCount={activityPlans.length}
              nickname={nickname}
              childStage={childStage}
              birthDate={birthDate}
              ageMonths={ageMonths}
              grade={grade}
              saving={saving}
              error={formError}
              onNicknameChange={setNickname}
              onStageChange={setChildStage}
              onBirthDateChange={handleBirthDateChange}
              onAgeMonthsChange={setAgeMonths}
              onGradeChange={setGrade}
              onSubmit={handleCreateChild}
              onSelectChild={(childId) => void handleSelectChild(childId)}
              onAvatarUpdated={handleAvatarUpdated}
            />
          )}

          {activeChild && showObservation && (
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
          )}

          {activeChild && showConversation && (
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
              onNewConversation={resetSearchConversation}
              onSelectConversation={selectConversation}
              backups={backups}
              backupBusy={backupBusy}
              backupError={backupError}
              backupNotice={backupNotice}
              onBackupCreate={handleCreateBackup}
              onBackupImport={handleImportBackup}
              onBackupExport={handleExportBackup}
              onBackupRestore={handleRestoreBackup}
            />
          )}

          {activeChild && showLibrary && (
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
          )}

          {activeChild && showMaterials && (
            childContext.materials.kind === "loading" ? (
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
                  handleUseMaterial,
                  handleReviewMaterial,
                  setRevisionNote,
                  handleReviseMaterial,
                  setEditingMaterialId,
                  handleParentEdit,
                  handlePrintMaterial,
                  handleMaterialResultRecorded,
                }}
              />
            )
          )}

          {activeChild && showActivities && activeChild.stage === "infant_0_2" && (
            <InfantGuidanceSection
              observationHints={observationHints}
              boardBooks={boardBooks}
              loading={infantGuidanceLoading}
              error={infantGuidanceError}
              onLoad={() => void handleLoadInfantGuidance()}
            />
          )}

          {activeChild && showActivities && (
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
          )}

          {activeChild && showTimeline && (
            <ObservationTimelineSection
              loadState={childContext.observations}
              timeline={timeline}
              activityPlans={activityPlans}
              onRetry={() => void reloadChildContextPart("observations")}
            />
          )}
        </section>
      )}

      {activeView === "backup" && (
        <DataManagementSection
          mode="backup"
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
      )}

      {activeView === "settings" && (
        <section className="settings-product-workspace" aria-labelledby="settings-product-title">
          <header className="settings-product-heading">
            <div>
              <p className="eyebrow">PREFERENCES</p>
              <h1 id="settings-product-title">설정</h1>
              <p>앱 상태, 가족 프로필과 개인정보 관련 설정을 관리합니다.</p>
            </div>
          </header>
          <SystemStatusSection
            connection={connection}
            activeChild={activeChild}
            childrenCount={children.length}
            onRefresh={() => refresh()}
          />
          <DataManagementSection
            mode="settings"
            showHeading={false}
            connected={isConnected}
            backups={backups}
            busy={backupBusy}
            error={backupError}
            notice={backupNotice}
            onImport={handleImportBackup}
            onCreate={() => void handleCreateBackup()}
            onExport={(archiveName) => void handleExportBackup(archiveName)}
            onRestore={handleRestoreBackup}
            onProfileUpdated={handleManagedProfileUpdated}
          />
        </section>
      )}

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
    </div>
  );
}

export default App;