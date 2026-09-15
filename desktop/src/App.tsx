import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { ConfirmDialog, MaterialWorkspaceIntegration, ViewStateNotice } from "./components";
import {
  childContextState,
  errorMessage,
  type ChildContextKey,
  type ChildContextLoadState,
  type ViewLoadState,
} from "./child-context-state";
import {
  appendConversationTurn,
  createActivity,
  createBackup,
  createChild,
  createConversation,
  createObservation,
  createResource,
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

const LAST_CHILD_KEY = "growwise:last-child-id";
const AXIS_OPTIONS: Array<{ value: ExperienceAxis; label: string }> = [
  { value: "physical", label: "신체" },
  { value: "emotional_character", label: "정서·인성" },
  { value: "expression_art", label: "표현·예술" },
  { value: "thinking_inquiry", label: "사고·탐구" },
  { value: "social", label: "사회성" },
  { value: "reading", label: "읽기" },
  { value: "speaking", label: "말하기" },
  { value: "writing", label: "쓰기" },
  { value: "math", label: "수학" },
  { value: "exploration", label: "탐색" },
];

function resultText(result: Record<string, unknown>): string {
  if (typeof result.parent_observation === "string") return result.parent_observation;
  if (typeof result.title === "string") return result.title;
  return "관련 기록";
}

function stageLabel(stage: Stage): string {
  return {
    infant_0_2: "영아 0~2세",
    preschool_3_5: "유아 3~5세",
    elementary: "초등",
    middle: "중등",
    high: "고등",
  }[stage];
}

function diversityLabel(state: GrowthMap["diversity"]["state"]): string {
  return {
    insufficient_data: "판단 보류",
    varied: "여러 경험이 관찰됨",
    mixed: "여러 경험과 반복이 함께 관찰됨",
    concentrated: "일부 경험이 자주 기록됨",
  }[state];
}

function axisLabel(axis: ExperienceAxis): string {
  return AXIS_OPTIONS.find((item) => item.value === axis)?.label ?? axis;
}

function activityStatusLabel(status: ActivityStatus): string {
  return {
    suggested: "제안됨",
    active: "진행 중",
    completed: "완료",
    skipped: "건너뜀",
    archived: "보관됨",
  }[status];
}

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
      if (requestId === childContextRequestId.current) updateChildContextState(key, { kind: "ready" });
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

  function retryAction(key: ChildContextKey) {
    return (
      <button className="quiet-button" type="button" onClick={() => void reloadChildContextPart(key)}>
        다시 시도
      </button>
    );
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
    } catch (error) {
      setResourceError(errorMessage(error, "자료 저장에 실패했습니다."));
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
  const mode = isConnected ? connection.health.operation_mode : null;
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

      <section className="status-grid" aria-label="시스템 상태">
        <article className="status-card primary-card">
          <div className="card-heading"><span className={`status-dot ${isConnected ? "ok" : "warning"}`} /><h2>GrowWise Core</h2></div>
          {connection.kind === "loading" && <p>확인 중입니다.</p>}
          {connection.kind === "offline" && <p className="muted">{connection.message}</p>}
          {connection.kind === "connected" && <><p className="status-title">정상 연결</p><p className="muted">{connection.runtime.started_by_desktop ? "Desktop이 Core를 자동 기동했습니다." : "실행 중인 Core에 연결했습니다."}</p></>}
        </article>
        <article className="status-card">
          <p className="card-label">운영 모드</p>
          <p className="status-title">{mode === "ai_enhanced_with_core_fallback" ? "AI 보강 + Core fallback" : mode === "core_only" ? "Core-only" : "확인 대기"}</p>
          {connection.kind === "connected" && <p className="muted">{connection.health.llm_configured ? connection.health.llm_reachable ? `${connection.health.model_provider} 연결됨` : `${connection.health.model_provider} 설정됨 · 현재 미도달` : "LLM 기능 꺼짐"}</p>}
        </article>
        <article className="status-card">
          <p className="card-label">현재 아이</p><p className="status-title">{activeChild?.nickname ?? "선택 안 됨"}</p><p className="muted">저장된 아이 {children.length}명 · child scope를 엄격히 분리합니다.</p>
        </article>
      </section>

      <section className="workspace">
        <div className="section-heading"><div><p className="eyebrow">CHILD CONTEXT</p><h2>기존 기록을 이어서 사용합니다.</h2></div><span className="badge">Pre-alpha</span></div>
        {children.length > 0 && <div className="child-switcher"><label><span>아이 선택</span><select value={activeChild?.id ?? ""} onChange={(event) => void handleSelectChild(event.target.value)}>{children.map((child) => <option key={child.id} value={child.id}>{child.nickname} · {stageLabel(child.stage)} · {child.age_months ?? "-"}개월</option>)}</select></label><p className="muted">마지막 선택을 기억하지만 데이터는 항상 Core에서 다시 조회합니다.</p></div>}

        <div className="skeleton-grid">
          <form className="profile-form" onSubmit={handleCreateChild}><p className="card-label">NEW CHILD</p><label><span>아이 닉네임</span><input value={nickname} onChange={(event) => setNickname(event.target.value)} placeholder="예: 샘플아이" maxLength={40} disabled={!isConnected || saving} /></label><label><span>교육 단계</span><select value={childStage} onChange={(event) => setChildStage(event.target.value as Stage)} disabled={!isConnected || saving}><option value="infant_0_2">영아 0~2세</option><option value="preschool_3_5">유아 3~5세</option><option value="elementary">초등</option><option value="middle">중등</option><option value="high">고등</option></select></label><label><span>월령(선택)</span><input type="number" min="0" max="240" value={ageMonths} onChange={(event) => setAgeMonths(event.target.value)} placeholder="예: 108" disabled={!isConnected || saving} /></label><button className="primary-button" type="submit" disabled={!isConnected || saving}>{saving ? "저장 중…" : "새 프로필 저장"}</button>{formError && <p className="form-error" role="alert">{formError}</p>}</form>
          <article className="verification-card">{activeChild ? <><p className="card-label">ACTIVE CONTEXT</p><h3>{activeChild.nickname}</h3><p className="muted">프로필은 선택 즉시 유지하고, 각 기록 영역은 Core에서 독립적으로 다시 불러옵니다.</p><dl className="verification-list"><div><dt>월령</dt><dd>{activeChild.age_months ?? "-"}개월</dd></div><div><dt>최근 기록</dt><dd>{childContext.growth.kind === "ready" && growthMap ? growthMap.total_logs_in_period : "—"}</dd></div><div><dt>활동</dt><dd>{childContext.activities.kind === "ready" ? activityPlans.length : "—"}</dd></div></dl></> : <><p className="card-label">EMPTY</p><h3>아이 프로필을 만들어 주세요.</h3></>}</article>
        </div>

        {!activeChild && connection.kind === "connected" && (
          <section className="child-context-required">
            <ViewStateNotice kind="empty" title="먼저 아이 프로필을 만들어 주세요." description="관찰, 성장, 활동, 자료, 검색 작업공간은 선택한 아이의 기록 범위 안에서 동작합니다." />
          </section>
        )}

        {activeChild && <>
          <div className="observation-panel">
            <form className="observation-form" onSubmit={handleCreateObservation}>
              <div><p className="card-label">OBSERVATION</p><h3>의미 있는 관찰만 기록합니다.</h3><p className="muted">관련 활동과 경험 축은 선택 사항입니다. 연결한 경우에만 활동의 후속 관찰로 기록됩니다.</p></div>
              <textarea value={observation} onChange={(event) => setObservation(event.target.value)} placeholder="예: 그림책의 고양이 그림을 오래 바라보고 여러 번 손으로 가리켰다." maxLength={10000} disabled={observationSaving} />
              {activityPlans.length > 0 && <label className="observation-activity-link"><span>관련 활동(선택)</span><select value={selectedActivityId} onChange={(event) => setSelectedActivityId(event.target.value)} disabled={observationSaving}><option value="">일반 관찰 기록</option>{activityPlans.filter((activity) => activity.status !== "archived").map((activity) => <option key={activity.id} value={activity.id}>{activity.title} · {activityStatusLabel(activity.status)}</option>)}</select></label>}
              <div className="axis-picker">{AXIS_OPTIONS.map((option) => { const active = selectedAxes.includes(option.value); return <button key={option.value} type="button" className={`axis-chip ${active ? "active" : ""}`} aria-pressed={active} onClick={() => toggleAxis(option.value)}>{option.label}</button>; })}</div>
              <button className="primary-button" type="submit" disabled={observationSaving}>{observationSaving ? "기록 중…" : "관찰 저장"}</button>
              {observationError && <p className="form-error" role="alert">{observationError}</p>}
            </form>
            <article className="observation-result">
              <p className="card-label">GROWTH CONTEXT</p><h3>최근 {growthMap?.period_days ?? 30}일</h3>
              {childContext.growth.kind === "loading" && <ViewStateNotice kind="loading" title="성장 맥락을 불러오는 중입니다." description="다른 작업공간은 기다리지 않고 사용할 수 있습니다." />}
              {childContext.growth.kind === "error" && <ViewStateNotice kind="error" title="성장 맥락을 불러오지 못했습니다." description={childContext.growth.message} action={retryAction("growth")} />}
              {childContext.growth.kind === "ready" && growthMap && growthMap.total_logs_in_period === 0 && <ViewStateNotice kind="empty" title="아직 최근 관찰 기록이 없습니다." description="관찰을 기록하면 경험 축과 성장 맥락이 이곳에 누적됩니다." />}
              {childContext.growth.kind === "ready" && growthMap && growthMap.total_logs_in_period > 0 && <><p className="muted">기록 {growthMap.total_logs_in_period}건 · 경험 축 연결 {growthMap.tagged_logs_in_period}건</p><div className="growth-layers">{growthMap.layers.map((layer) => <section className="growth-layer" key={layer.key}><strong>{layer.label}</strong><div className="axis-summary">{layer.axes.filter((axis) => axis.observation_count > 0).map((axis) => <span key={axis.axis}>{axisLabel(axis.axis)} · {axis.observation_count}</span>)}</div>{layer.axes.every((axis) => axis.observation_count === 0) && <small>이 렌즈에 연결된 최근 기록이 아직 없습니다.</small>}</section>)}</div><div className={`diversity-note diversity-${growthMap.diversity.state}`}><strong>{diversityLabel(growthMap.diversity.state)}</strong><p>{growthMap.diversity.note}</p>{growthMap.diversity.focus_axes.length > 0 && <small>자주 기록된 경험: {growthMap.diversity.focus_axes.map(axisLabel).join(", ")}</small>}</div></>}
            </article>
          </div>

          <section className="search-section"><p className="card-label">NATURAL-LANGUAGE SEARCH</p><h3>기록을 자연어로 찾습니다.</h3><p className="muted">AI가 없어도 child-scoped lexical 검색이 작동합니다.</p><form className="search-form" onSubmit={handleSearch}><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="예: 고양이 그림에 관심 보인 기록 찾아줘" /><button className="primary-button" type="submit" disabled={searching}>{searching ? "검색 중…" : "검색"}</button></form>{searchError && <p className="form-error" role="alert">{searchError}</p>}{searchResult && <div className="search-results"><p className="muted">검색 키워드: {searchResult.plan.keywords.join(", ") || "원문 사용"} · 결과 {searchResult.results.length}건</p>{searchResult.results.length === 0 ? <ViewStateNotice kind="empty" title="일치하는 기록이 없습니다." description="검색어를 조금 넓히거나 다른 표현으로 다시 찾아보세요." /> : searchResult.results.map((result, index) => <article className="search-result-card" key={String(result.id ?? index)}><p>{resultText(result)}</p></article>)}</div>}</section>

          <section className="conversation-section"><p className="card-label">BOUNDED MULTI-TURN</p><h3>후속 질문으로 맥락을 좁힙니다.</h3><p className="muted">대화는 지시어 해석에만 쓰고, 사실 근거는 매 턴 원본 기록과 Resource KB에서 다시 찾습니다.</p><form className="search-form" onSubmit={handleConversation}><input value={conversationQuestion} onChange={(event) => setConversationQuestion(event.target.value)} placeholder="예: 그중 고양이 관련 기록만 보여줘" /><button className="primary-button" type="submit" disabled={conversationBusy}>{conversationBusy ? "확인 중…" : conversation ? "후속 질문" : "세션 시작"}</button></form>{conversationError && <p className="form-error" role="alert">{conversationError}</p>}{conversation && <p className="muted session-meta">session {conversation.id.slice(0, 8)}… · child scope 고정</p>}<div className="conversation-list">{conversationAnswers.map((item, index) => <article className="conversation-card" key={`${item.session_id}-${index}`}><p>{item.answer.answer}</p><small>{item.answer.source_ids.length > 0 ? `근거 ${item.answer.source_ids.length}건 · ${item.answer.source_ids.join(", ")}` : item.answer.insufficient_evidence ? "근거 부족" : "근거 없음"}</small></article>)}</div></section>

          <section className="resource-section"><div className="resource-grid"><form className="resource-form" onSubmit={handleCreateResource}><p className="card-label">RESOURCE LIBRARY</p><h3>자료를 지식베이스에 넣습니다.</h3><label><span>종류</span><select value={resourceKind} onChange={(event) => setResourceKind(event.target.value as ResourceKind)}><option value="note">메모</option><option value="book">도서</option><option value="curriculum">교육과정</option><option value="web">웹 자료</option><option value="file">파일 메모</option></select></label><label><span>제목</span><input value={resourceTitle} onChange={(event) => setResourceTitle(event.target.value)} maxLength={500} /></label><label><span>내용</span><textarea value={resourceContent} onChange={(event) => setResourceContent(event.target.value)} placeholder="자료의 핵심 내용이나 메모" /></label><button className="primary-button" type="submit" disabled={resourceSaving}>{resourceSaving ? "저장 중…" : "자료 저장"}</button>{resourceError && <p className="form-error" role="alert">{resourceError}</p>}</form><div className="resource-list"><p className="card-label">INDEXED RESOURCES</p><h3>{childContext.library.kind === "ready" ? `${resources.length}건` : "자료 목록"}</h3>{childContext.library.kind === "loading" && <ViewStateNotice kind="loading" title="자료 목록을 불러오는 중입니다." description="저장된 자료를 아이 범위에 맞춰 확인합니다." />}{childContext.library.kind === "error" && <ViewStateNotice kind="error" title="자료 목록을 불러오지 못했습니다." description={childContext.library.message} action={retryAction("library")} />}{childContext.library.kind === "ready" && resources.length === 0 ? <ViewStateNotice kind="empty" title="연결된 자료가 아직 없습니다." description="메모, 책, 교육과정 또는 웹 자료를 저장하면 여기에 모입니다." /> : null}{childContext.library.kind === "ready" && resources.map((resource) => <article className="resource-card" key={resource.id}><strong>{resource.title}</strong><span>{resource.kind}</span>{resource.content && <p>{resource.content}</p>}</article>)}</div></div></section>

          {childContext.materials.kind === "loading" ? (
            <section className="material-workspace material-state-panel"><ViewStateNotice kind="loading" title="생성 자료를 불러오는 중입니다." description="다른 작업공간은 계속 사용할 수 있습니다." /></section>
          ) : childContext.materials.kind === "error" ? (
            <section className="material-workspace material-state-panel"><ViewStateNotice kind="error" title="생성 자료를 불러오지 못했습니다." description={childContext.materials.message} action={retryAction("materials")} /></section>
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
            <section className="infant-guidance-section">
              <div className="activity-heading">
                <div>
                  <p className="card-label">INFANT OBSERVATION GUIDE</p>
                  <h3>관찰 힌트와 보드북 연결</h3>
                  <p className="muted">진단 체크리스트가 아니라 일상에서 무엇을 살펴볼지 돕습니다.</p>
                </div>
                <button className="quiet-button" type="button" onClick={() => void handleLoadInfantGuidance()} disabled={infantGuidanceLoading}>{infantGuidanceLoading ? "불러오는 중…" : "관찰 힌트·책 보기"}</button>
              </div>
              {infantGuidanceError && <p className="form-error" role="alert">{infantGuidanceError}</p>}
              {(observationHints || boardBooks) && <div className="resource-grid"><div className="resource-list"><p className="card-label">OBSERVATION HINTS</p><h3>{observationHints?.hints.length ?? 0}개 영역</h3>{observationHints?.hints.map((hint) => <article className="resource-card" key={hint.domain}><strong>{hint.domain}</strong><p>{hint.cue}</p><small>{hint.rationale}</small></article>)}{observationHints && <p className="muted">{observationHints.source} · 진단용 아님</p>}</div><div className="resource-list"><p className="card-label">BOARD BOOKS</p><h3>{boardBooks?.recommendations.length ?? 0}권</h3>{boardBooks?.recommendations.map((book) => <article className="resource-card" key={`${book.resource_id ?? book.title}-${book.title}`}><strong>{book.title}</strong><p>{book.reason}</p><small>{book.read_aloud_tip}</small></article>)}</div></div>}
            </section>
          )}

          <section className="activity-section"><div className="activity-heading"><div><p className="card-label">ACTIVITY INVITATIONS</p><h3>다음 활동 후보</h3><p className="muted">추천은 의무가 아닙니다. 부모가 선택한 후보만 활동 목록에 저장됩니다.</p></div><button className="quiet-button" type="button" onClick={() => void handleLoadActivities()} disabled={activitiesLoading}>{activitiesLoading ? "불러오는 중…" : "활동 후보 보기"}</button></div>{activitiesError && <p className="form-error" role="alert">{activitiesError}</p>}{activities && <div className="activity-grid">{activities.suggestions.map((suggestion) => <article className="activity-card" key={`${suggestion.title}-${suggestion.description}`}><h4>{suggestion.title}</h4><p>{suggestion.description}</p>{suggestion.observation_cue && <small>{suggestion.observation_cue}</small>}<button type="button" className="quiet-button activity-save" disabled={activityPlanBusy} onClick={() => void handleSaveActivity(suggestion.title)}>활동으로 저장</button></article>)}</div>}</section>

          <section className="quest-section"><div className="activity-heading"><div><p className="card-label">ACTIVITY QUESTS</p><h3>선택한 활동</h3><p className="muted">건너뜀은 실패가 아니며, 나중에 다시 시작할 수 있습니다.</p></div><span className="badge">{childContext.activities.kind === "ready" ? `${activityPlans.length}건` : "확인 중"}</span></div>{childContext.activities.kind === "loading" && <ViewStateNotice kind="loading" title="활동 목록을 불러오는 중입니다." description="저장한 활동 상태를 확인합니다." />}{childContext.activities.kind === "error" && <ViewStateNotice kind="error" title="활동 목록을 불러오지 못했습니다." description={childContext.activities.message} action={retryAction("activities")} />}{childContext.activities.kind === "ready" && activityPlans.length === 0 ? <ViewStateNotice kind="empty" title="저장한 활동이 없습니다." description="활동 후보에서 선택한 항목만 이 목록에 저장됩니다." /> : null}{childContext.activities.kind === "ready" && activityPlans.length > 0 && <div className="quest-list">{activityPlans.map((activity) => <article className="quest-card" key={activity.id}><div><strong>{activity.title}</strong><span className={`status-badge status-${activity.status}`}>{activityStatusLabel(activity.status)}</span></div>{activity.parent_note && <p>{activity.parent_note}</p>}<div className="review-actions">{activity.status === "suggested" && <button type="button" className="primary-button" disabled={activityPlanBusy} onClick={() => void handleActivityTransition(activity.id, "active")}>시작</button>}{activity.status === "active" && <button type="button" className="primary-button" disabled={activityPlanBusy} onClick={() => void handleActivityTransition(activity.id, "completed")}>완료</button>}{(activity.status === "suggested" || activity.status === "active") && <button type="button" className="quiet-button" disabled={activityPlanBusy} onClick={() => void handleActivityTransition(activity.id, "skipped")}>건너뜀</button>}{activity.status === "skipped" && <button type="button" className="quiet-button" disabled={activityPlanBusy} onClick={() => void handleActivityTransition(activity.id, "active")}>다시 시작</button>}</div></article>)}</div>}</section>

          <section className="timeline-section"><div className="activity-heading"><div><p className="card-label">OBSERVATION TIMELINE</p><h3>관찰 기록</h3></div><span className="badge">{childContext.observations.kind === "ready" ? `${timeline.length}건` : "확인 중"}</span></div>{childContext.observations.kind === "loading" && <ViewStateNotice kind="loading" title="관찰 기록을 불러오는 중입니다." description="이 아이의 기록만 확인합니다." />}{childContext.observations.kind === "error" && <ViewStateNotice kind="error" title="관찰 기록을 불러오지 못했습니다." description={childContext.observations.message} action={retryAction("observations")} />}{childContext.observations.kind === "ready" && timeline.length === 0 ? <ViewStateNotice kind="empty" title="아직 기록이 없습니다." description="기록 공백은 실패가 아닙니다. 의미 있는 순간이 있을 때만 남겨도 됩니다." /> : null}{childContext.observations.kind === "ready" && timeline.length > 0 && <div className="timeline-list">{timeline.map((log) => { const linkedActivity = log.activity_plan_id ? activityPlans.find((item) => item.id === log.activity_plan_id) : null; return <article key={log.id} className="timeline-card">{linkedActivity && <small className="timeline-activity">활동 · {linkedActivity.title}</small>}<p>{log.parent_observation}</p><div className="axis-summary">{log.experience_axes.map((axis) => <span key={axis}>{AXIS_OPTIONS.find((item) => item.value === axis)?.label ?? axis}</span>)}</div>{log.created_at && <time dateTime={log.created_at}>{new Date(log.created_at).toLocaleString("ko-KR")}</time>}</article>; })}</div>}</section>
        </>}
      </section>

      <section className="data-management-section">
        <div className="activity-heading"><div><p className="card-label">DATA MANAGEMENT</p><h2>백업과 복원</h2><p className="muted">Markdown 정본을 portable ZIP으로 보관하고, 복원 시 검색 인덱스를 다시 만듭니다.</p></div><div className="review-actions"><button className="quiet-button" type="button" onClick={handleImportBackup} disabled={!isConnected || backupBusy}>외부 ZIP 가져오기</button><button className="quiet-button" type="button" onClick={() => void handleCreateBackup()} disabled={!isConnected || backupBusy}>{backupBusy ? "처리 중…" : "지금 백업"}</button></div></div>
        {backupError && <p className="form-error" role="alert">{backupError}</p>}
        {backupNotice && <p className="muted" role="status" aria-live="polite">{backupNotice}</p>}
        {backups.length === 0 ? <p className="muted">아직 만든 백업이 없습니다.</p> : <div className="quest-list">{backups.map((backup) => <article className="quest-card" key={backup.archive}><div><strong>{backup.archive}</strong><span className="status-badge">{Math.max(1, Math.round(backup.size_bytes / 1024))} KB</span></div><p>{new Date(backup.modified_at).toLocaleString("ko-KR")}</p><div className="review-actions"><button className="quiet-button" type="button" disabled={backupBusy} onClick={() => void handleExportBackup(backup.archive)}>ZIP 내보내기</button><button className="quiet-button" type="button" disabled={backupBusy} onClick={() => handleRestoreBackup(backup.archive)}>이 백업 복원</button></div></article>)}</div>}
      </section>

      <ConfirmDialog open={backupConfirmation !== null} title={backupConfirmationTitle} description={backupConfirmationDescription} confirmLabel={backupConfirmationLabel} busy={backupBusy} destructive onConfirm={() => void handleConfirmBackupAction()} onCancel={handleCancelBackupAction} />

      {printMaterial && <article className="print-material" aria-hidden="true"><h1>{printMaterial.title}</h1><pre>{printMaterial.content_markdown}</pre></article>}
    </main>
  );
}

export default App;
