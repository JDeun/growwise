import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

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
  type ChildContextKey,
  type ChildContextLoadState,
  type ViewLoadState,
} from "./child-context-state";
import { activityStatusLabel } from "./presentation";
import {
  appendConversationTurn,
  createActivity,
  createBackup,
  createChild,
  createConversation,
  createObservation,
  createResource,
  deleteResource,
  exportBackup,
  editMaterial,
  generateMaterial,
  getBoardBookRecommendations,
  getCoreRuntimeStatus,
  getGrowthMap,
  getHealth,
  getInfantActivities,
  getInfantObservationHints,
  importBackup,
  listActivities,
  listBackups,
  listChildren,
  listMaterials,
  listObservations,
  listResources,
  restoreBackup,
  reviewMaterial,
  reviseMaterial,
  searchChildContext,
  transitionActivity,
  updateResource,
  type ActivityPlan,
  type ActivityStatus,
  type BackupItem,
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
  type MaterialKind,
  type MaterialStatus,
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

type BackupConfirmation =
  | { kind: "import" }
  | { kind: "restore"; archiveName: string };

type WriteNotice = { id: number; message: string };

const LAST_CHILD_KEY = "growwise:last-child-id";

function App() {
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

  const [materialKind, setMaterialKind] = useState<MaterialKind>("activity_guide");
  const [materialTopic, setMaterialTopic] = useState("");
  const [materialGoal, setMaterialGoal] = useState("");
  const [selectedResourceRefs, setSelectedResourceRefs] = useState<string[]>([]);
  const [materialBusy, setMaterialBusy] = useState(false);
  const [materialError, setMaterialError] = useState<string | null>(null);
  const [revisionNotes, setRevisionNotes] = useState<Record<string, string>>({});
  const [editingMaterialId, setEditingMaterialId] = useState<string | null>(null);

  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [backupBusy, setBackupBusy] = useState(false);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [backupNotice, setBackupNotice] = useState<string | null>(null);
  const [backupConfirmation, setBackupConfirmation] = useState<BackupConfirmation | null>(null);
  const [printMaterial, setPrintMaterial] = useState<GeneratedMaterial | null>(null);
  const [writeNotice, setWriteNotice] = useState<WriteNotice | null>(null);
  const writeNoticeId = useRef(0);

  const updateChildContextState = useCallback((key: ChildContextKey, state: ViewLoadState) => {
    setChildContext((current) => ({ ...current, [key]: state }));
  }, []);

  const loadChildContext = useCallback(async (child: ChildProfile) => {
    const requestId = ++childContextRequestId.current;
    setActiveChild(child);
    setGrowthMap(null);
    setTimeline([]);
    setResources([]);
    setMaterials([]);
    setActivityPlans([]);
    setChildContext(childContextState("loading"));
    setSelectedResourceRefs([]);
    setSelectedActivityId("");
    setActivities(null);
    setObservationHints(null);
    setBoardBooks(null);
    setInfantGuidanceError(null);
    setSearchResult(null);
    setSearchError(null);
    setConversation(null);
    setConversationAnswers([]);
    setConversationError(null);
    localStorage.setItem(LAST_CHILD_KEY, child.id);

    const [growthResult, observationsResult, resourcesResult, materialsResult, activitiesResult] =
      await Promise.allSettled([
        getGrowthMap(child.id),
        listObservations(child.id),
        listResources(child.id),
        listMaterials(child.id),
        listActivities(child.id),
      ]);

    if (requestId !== childContextRequestId.current) return;

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

      try {
        setBackups(await listBackups());
        setBackupError(null);
      } catch (error) {
        setBackups([]);
        setBackupError(errorMessage(error, "백업 목록을 불러오지 못했습니다."));
      }

      if (storedChildren.length > 0) {
        const rememberedId = localStorage.getItem(LAST_CHILD_KEY);
        const selected =
          storedChildren.find((child) => child.id === rememberedId) ?? storedChildren[0];
        await loadChildContext(selected);
      } else {
        childContextRequestId.current += 1;
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
      setConnection({
        kind: "offline",
        message: errorMessage(error, "GrowWise Core 상태를 확인할 수 없습니다."),
      });
    }
  }, [loadChildContext]);

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
    updateChildContextState(key, { kind: "loading" });

    try {
      if (key === "growth") {
        const value = await getGrowthMap(childId);
        if (requestId !== childContextRequestId.current) return;
        setGrowthMap(value);
      } else if (key === "observations") {
        const value = await listObservations(childId);
        if (requestId !== childContextRequestId.current) return;
        setTimeline(value);
      } else if (key === "library") {
        const value = await listResources(childId);
        if (requestId !== childContextRequestId.current) return;
        setResources(value);
      } else if (key === "materials") {
        const value = await listMaterials(childId);
        if (requestId !== childContextRequestId.current) return;
        setMaterials(value);
      } else {
        const value = await listActivities(childId);
        if (requestId !== childContextRequestId.current) return;
        setActivityPlans(value);
      }
      if (requestId === childContextRequestId.current) {
        updateChildContextState(key, { kind: "ready" });
      }
    } catch (error) {
      if (requestId !== childContextRequestId.current) return;
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
    const text = observation.trim();
    if (!text) return setObservationError("기억할 가치가 있는 관찰을 짧게 적어 주세요.");
    setObservationSaving(true);
    setObservationError(null);
    try {
      await createObservation({
        child_id: activeChild.id,
        observation: text,
        experience_axes: selectedAxes,
        activity_plan_id: selectedActivityId || null,
      });
      setObservation("");
      setSelectedAxes([]);
      setSelectedActivityId("");
      setActivities(null);
      setSearchResult(null);
      await Promise.all([
        reloadChildContextPart("growth"),
        reloadChildContextPart("observations"),
      ]);
      announceWrite("관찰 기록을 저장했습니다.");
    } catch (error) {
      setObservationError(errorMessage(error, "관찰 기록 저장에 실패했습니다."));
    } finally {
      setObservationSaving(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const query = searchQuery.trim();
    if (query.length < 2) return setSearchError("두 글자 이상으로 검색해 주세요.");
    setSearching(true);
    setSearchError(null);
    try {
      setSearchResult(await searchChildContext(activeChild.id, query));
    } catch (error) {
      setSearchError(errorMessage(error, "검색에 실패했습니다."));
    } finally {
      setSearching(false);
    }
  }

  async function handleConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const question = conversationQuestion.trim();
    if (question.length < 2) return setConversationError("두 글자 이상으로 질문해 주세요.");
    setConversationBusy(true);
    setConversationError(null);
    try {
      let session = conversation;
      if (!session) {
        session = await createConversation(activeChild.id);
        setConversation(session);
      }
      const answer = await appendConversationTurn(session.id, question);
      setConversationAnswers((current) => [...current, answer]);
      setConversationQuestion("");
    } catch (error) {
      setConversationError(errorMessage(error, "후속 질문 처리에 실패했습니다."));
    } finally {
      setConversationBusy(false);
    }
  }

  async function handleCreateResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const title = resourceTitle.trim();
    const content = resourceContent.trim();
    if (!title) return setResourceError("자료 제목을 입력해 주세요.");
    setResourceSaving(true);
    setResourceError(null);
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
      setResourceTitle("");
      setResourceContent("");
      await reloadChildContextPart("library");
      announceWrite("자료를 저장했습니다.");
    } catch (error) {
      setResourceError(errorMessage(error, "자료 저장에 실패했습니다."));
    } finally {
      setResourceSaving(false);
    }
  }

  async function handleUpdateResource(resourceId: string, request: ResourceCreateInput) {
    setResourceSaving(true);
    setResourceError(null);
    try {
      const updated = await updateResource(resourceId, request);
      setResources((current) =>
        current.map((resource) => (resource.id === updated.id ? updated : resource)),
      );
      announceWrite("자료를 수정했습니다.");
    } catch (error) {
      setResourceError(errorMessage(error, "자료 수정에 실패했습니다."));
      throw error;
    } finally {
      setResourceSaving(false);
    }
  }

  async function handleDeleteResource(resourceId: string) {
    setResourceSaving(true);
    setResourceError(null);
    try {
      await deleteResource(resourceId);
      setResources((current) => current.filter((resource) => resource.id !== resourceId));
      setSelectedResourceRefs((current) =>
        current.filter((ref) => ref !== `resource:${resourceId}`),
      );
      announceWrite("자료를 삭제했습니다.");
    } catch (error) {
      setResourceError(errorMessage(error, "자료 삭제에 실패했습니다."));
      throw error;
    } finally {
      setResourceSaving(false);
    }
  }

  async function handleGenerateMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChild) return;
    const topic = materialTopic.trim();
    if (!topic) return setMaterialError("자료 주제를 입력해 주세요.");
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await generateMaterial(
        activeChild.id,
        materialKind,
        topic,
        materialGoal.trim() || undefined,
        selectedResourceRefs,
      );
      setMaterialTopic("");
      setMaterialGoal("");
      setSelectedResourceRefs([]);
      await reloadChildContextPart("materials");
      announceWrite("학습 자료 초안을 생성했습니다.");
    } catch (error) {
      setMaterialError(errorMessage(error, "자료 생성에 실패했습니다."));
    } finally {
      setMaterialBusy(false);
    }
  }

  async function handleReviewMaterial(materialId: string, status: MaterialStatus) {
    if (!activeChild) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await reviewMaterial(materialId, status);
      await reloadChildContextPart("materials");
      announceWrite(
        status === "approved"
          ? "학습 자료를 승인했습니다."
          : status === "rejected"
            ? "학습 자료를 반려했습니다."
            : "자료 검토 상태를 변경했습니다.",
      );
    } catch (error) {
      setMaterialError(errorMessage(error, "자료 검토 상태 변경에 실패했습니다."));
    } finally {
      setMaterialBusy(false);
    }
  }

  async function handleReviseMaterial(materialId: string) {
    if (!activeChild) return;
    const note = (revisionNotes[materialId] ?? "").trim();
    if (!note) return setMaterialError("수정할 내용을 짧게 적어 주세요.");
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await reviseMaterial(materialId, note);
      await reloadChildContextPart("materials");
      setRevisionNotes((current) => {
        const next = { ...current };
        delete next[materialId];
        return next;
      });
      announceWrite("수정본을 생성했습니다.");
    } catch (error) {
      setMaterialError(errorMessage(error, "수정본 생성에 실패했습니다."));
    } finally {
      setMaterialBusy(false);
    }
  }

  async function handleParentEdit(
    materialId: string,
    title: string,
    contentMarkdown: string,
    note: string | null,
  ) {
    if (!activeChild) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await editMaterial(materialId, title, contentMarkdown, note);
      await reloadChildContextPart("materials");
      setEditingMaterialId(null);
      announceWrite("편집본을 저장했습니다.");
    } catch (error) {
      setMaterialError(errorMessage(error, "편집본 저장에 실패했습니다."));
    } finally {
      setMaterialBusy(false);
    }
  }

  async function handleLoadActivities() {
    if (!activeChild) return;
    setActivitiesLoading(true);
    setActivitiesError(null);
    try {
      setActivities(await getInfantActivities(activeChild.id));
    } catch (error) {
      setActivitiesError(errorMessage(error, "활동 후보를 불러오지 못했습니다."));
    } finally {
      setActivitiesLoading(false);
    }
  }

  async function handleLoadInfantGuidance() {
    if (!activeChild) return;
    setInfantGuidanceLoading(true);
    setInfantGuidanceError(null);
    try {
      const [hints, books] = await Promise.all([
        getInfantObservationHints(activeChild.id),
        getBoardBookRecommendations(activeChild.id),
      ]);
      setObservationHints(hints);
      setBoardBooks(books);
    } catch (error) {
      setInfantGuidanceError(errorMessage(error, "영아 관찰 가이드를 불러오지 못했습니다."));
    } finally {
      setInfantGuidanceLoading(false);
    }
  }

  async function handleSaveActivity(title: string) {
    if (!activeChild) return;
    setActivityPlanBusy(true);
    setActivitiesError(null);
    try {
      await createActivity(activeChild.id, title);
      await reloadChildContextPart("activities");
      announceWrite("활동으로 저장했습니다.");
    } catch (error) {
      setActivitiesError(errorMessage(error, "활동 저장에 실패했습니다."));
    } finally {
      setActivityPlanBusy(false);
    }
  }

  async function handleActivityTransition(activityId: string, status: ActivityStatus) {
    if (!activeChild) return;
    setActivityPlanBusy(true);
    setActivitiesError(null);
    try {
      await transitionActivity(activityId, status);
      await reloadChildContextPart("activities");
      announceWrite(`활동 상태를 '${activityStatusLabel(status)}'으로 변경했습니다.`);
    } catch (error) {
      setActivitiesError(errorMessage(error, "활동 상태 변경에 실패했습니다."));
    } finally {
      setActivityPlanBusy(false);
    }
  }

  async function handleCreateBackup() {
    setBackupBusy(true);
    setBackupError(null);
    setBackupNotice(null);
    try {
      await createBackup();
      setBackups(await listBackups());
      setBackupNotice("새 백업을 만들었습니다.");
    } catch (error) {
      setBackupError(errorMessage(error, "백업 생성에 실패했습니다."));
    } finally {
      setBackupBusy(false);
    }
  }

  async function handleExportBackup(archiveName: string) {
    setBackupBusy(true);
    setBackupError(null);
    setBackupNotice(null);
    try {
      await exportBackup(archiveName);
      setBackupNotice("백업 ZIP 내보내기를 완료했습니다.");
    } catch (error) {
      setBackupError(errorMessage(error, "백업 내보내기에 실패했습니다."));
    } finally {
      setBackupBusy(false);
    }
  }

  function handleImportBackup() {
    if (backupBusy) return;
    setBackupError(null);
    setBackupNotice(null);
    setBackupConfirmation({ kind: "import" });
  }

  function handleRestoreBackup(archiveName: string) {
    if (backupBusy) return;
    setBackupError(null);
    setBackupNotice(null);
    setBackupConfirmation({ kind: "restore", archiveName });
  }

  async function handleConfirmBackupAction() {
    const action = backupConfirmation;
    if (!action) return;
    setBackupBusy(true);
    setBackupError(null);
    setBackupNotice(null);
    try {
      if (action.kind === "import") {
        const result = await importBackup();
        if (result) {
          await refresh();
          setBackupNotice("외부 백업을 가져왔습니다.");
        }
      } else {
        await restoreBackup(action.archiveName);
        await refresh();
        setBackupNotice("백업을 복원했습니다.");
      }
      setBackupConfirmation(null);
    } catch (error) {
      setBackupError(
        errorMessage(
          error,
          action.kind === "import"
            ? "외부 백업 가져오기에 실패했습니다."
            : "백업 복원에 실패했습니다.",
        ),
      );
    } finally {
      setBackupBusy(false);
    }
  }

  function handleCancelBackupAction() {
    if (!backupBusy) setBackupConfirmation(null);
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

  function toggleResourceRef(resourceId: string) {
    const ref = `resource:${resourceId}`;
    setSelectedResourceRefs((current) =>
      current.includes(ref) ? current.filter((item) => item !== ref) : [...current, ref],
    );
  }

  const isConnected = connection.kind === "connected";
  const backupConfirmationTitle =
    backupConfirmation?.kind === "restore" ? "백업으로 복원하기" : "외부 백업 가져오기";
  const backupConfirmationDescription =
    backupConfirmation?.kind === "restore"
      ? `현재 기록을 ${backupConfirmation.archiveName} 백업으로 교체합니다. 복원 전에 현재 상태를 별도 백업하는 것을 권장합니다.`
      : "외부 GrowWise ZIP을 가져오면 현재 기록을 교체합니다. 가져오기 직전에 현재 상태를 자동 보호 백업합니다.";
  const backupConfirmationLabel =
    backupConfirmation?.kind === "restore" ? "이 백업 복원" : "가져오기 계속";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <img className="brand-logo" src="/growwise-symbol.svg" alt="" aria-hidden="true" />
          <div><strong>GrowWise</strong><span>Personal Education OS</span></div>
        </div>
        <button className="quiet-button" type="button" onClick={() => void refresh()}>새로고침</button>
      </header>

      <section className="hero">
        <p className="eyebrow">LOCAL-FIRST · PARENT-LED</p>
        <h1>아이의 배움을 기록하고, 필요한 맥락을 연결합니다.</h1>
        <p className="hero-copy">핵심 기록·검색·자료 관리는 AI 없이도 동작합니다. 로컬 모델은 정리와 검색, 생성을 선택적으로 보강합니다.</p>
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
                  setRevisionNote: (materialId, note) =>
                    setRevisionNotes((current) => ({ ...current, [materialId]: note })),
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
