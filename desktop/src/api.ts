import { invoke } from "@tauri-apps/api/core";

export type OperationMode = "ai_enhanced_with_core_fallback" | "core_only";
export type Stage = "infant_0_2" | "preschool_3_5" | "elementary" | "middle" | "high";
export type ExperienceAxis = "physical" | "emotional_character" | "expression_art" | "thinking_inquiry" | "social" | "reading" | "speaking" | "writing" | "math" | "exploration";
export type ActivityStatus = "suggested" | "active" | "completed" | "skipped" | "archived";
export type ResourceKind = "book" | "curriculum" | "web" | "note" | "file";
export type MaterialKind = "activity_guide" | "reading_activity" | "english_card" | "math_activity" | "science_inquiry" | "writing_prompt" | "field_trip";
export type MaterialStatus = "draft" | "review_pending" | "revision_requested" | "approved" | "rejected" | "archived";
export type PhotoRecordStatus = "queued" | "processing" | "draft" | "committed" | "failed" | "discarded";

export interface HealthResponse { status: string; operation_mode: OperationMode; core_requires_llm: boolean; llm_configured: boolean; llm_reachable: boolean; llm_features_enabled: boolean; embedding_features_enabled: boolean; model_provider: string; }
export interface CoreRuntimeStatus { started_by_desktop: boolean; }
export interface ChildCreateInput { nickname: string; stage: Stage; age_months: number | null; interests: string[]; }
export interface ChildProfile { id: string; nickname: string; stage: Stage; age_months: number | null; interests: string[]; }
export interface ChildPurgeResult { child_id: string; markdown_files_deleted: number; photo_files_deleted: number; rag_chunks_deleted: number; conversations_deleted: number; jobs_deleted: number; idempotency_records_deleted: number; checkpoint_threads_deleted: number; links_deleted: number; backups_may_contain_deleted_child: boolean; }
export interface ObservationCreateInput { child_id: string; observation: string; experience_axes: ExperienceAxis[]; activity_plan_id?: string | null; }
export interface LearningLog { id: string; child_id: string; activity_plan_id: string | null; parent_observation: string; tags: string[]; experience_axes: ExperienceAxis[]; interest: string | null; next_activity: string | null; created_at: string | null; }
export interface GrowthAxis { axis: ExperienceAxis; state: string; observation_count: number; }
export interface GrowthLayer { key: "whole_person" | "learning" | "stage_focus"; label: string; axes: GrowthAxis[]; }
export type DiversityState = "insufficient_data" | "varied" | "mixed" | "concentrated";
export interface CoverageDiversity { state: DiversityState; observed_axis_count: number; focus_axes: ExperienceAxis[]; note: string; }
export interface GrowthMap { child_id: string; period_days: number; stage: Stage | null; total_logs_in_period: number; tagged_logs_in_period: number; axes: GrowthAxis[]; layers: GrowthLayer[]; diversity: CoverageDiversity; }
export interface ActivitySuggestion { title: string; description: string; materials: string[]; observation_cue: string | null; tags: string[]; }
export interface InfantActivitySuggestions { suggestions: ActivitySuggestion[]; }
export interface ObservationHint { domain: string; cue: string; rationale: string; }
export interface InfantObservationHints { source: string; effective_date: string; diagnostic: boolean; hints: ObservationHint[]; }
export interface BoardBookRecommendation { resource_id: string | null; title: string; reason: string; read_aloud_tip: string; source: string; }
export interface BoardBookRecommendations { recommendations: BoardBookRecommendation[]; }
export interface ActivityPlan { id: string; child_id: string; title: string; status: ActivityStatus; source_refs: string[]; parent_note: string | null; started_at: string | null; completed_at: string | null; skipped_at: string | null; created_at?: string; updated_at?: string; }
export interface SearchPlan { keywords: string[]; entity_types: string[]; limit: number; }
export interface SearchResponse { query: string; plan: SearchPlan; results: Array<Record<string, unknown>>; }
export interface ConversationSession { id: string; child_id: string; title: string | null; turns: Array<{ role: "user" | "assistant"; content: string; source_ids: string[]; created_at: string; }>; created_at?: string; updated_at?: string; }
export interface ConversationAnswer { session_id: string; thread_id: string; answer: { answer: string; source_ids: string[]; insufficient_evidence: boolean; }; turn_count: number; }
export interface ResourceCreateInput { kind: ResourceKind; title: string; child_id: string | null; summary: string | null; content: string | null; source_url: string | null; source_name: string | null; author: string | null; tags: string[]; stage_tags: string[]; provenance: Record<string, string>; }
export interface ResourceRecord extends ResourceCreateInput { id: string; created_at?: string; updated_at?: string; }
export interface CurriculumTarget { mapping_id: string; framework: string; domain: string; description: string; source_ref: string; standard_codes: string[]; }
export interface GeneratedMaterial { id: string; child_id: string; kind: MaterialKind; title: string; content_markdown: string; status: MaterialStatus; source_refs: string[]; curriculum_targets?: CurriculumTarget[]; generator_mode: string; review_note: string | null; request_topic: string | null; request_goal: string | null; version: number; parent_material_id: string | null; version_note: string | null; created_at?: string; updated_at?: string; }
export interface PhotoUploadInput { filename: string; mime_type: string; data_base64: string; }
export interface PhotoAsset { id: string; child_id: string; original_filename: string; mime_type: string; relative_path: string; sha256: string; byte_size: number; width: number | null; height: number | null; captured_at: string | null; metadata_summary: Record<string, string>; caption: string | null; caption_model: string | null; }
export interface PhotoActivityRecord { id: string; child_id: string; photo_asset_ids: string[]; user_context: string | null; generated_observation: string; generation_mode: string; status: PhotoRecordStatus; job_id: string | null; error_message: string | null; suggested_tags: string[]; suggested_experience_axes: ExperienceAxis[]; suggested_interest: string | null; suggested_difficulty_note: string | null; suggested_next_activity: string | null; learning_log_id: string | null; created_at?: string; updated_at?: string; }
export interface PhotoJobSummary { id: string; status: "pending" | "running" | "completed" | "failed" | "cancelled"; attempts: number; }
export interface PhotoDraftResult { record: PhotoActivityRecord; assets: PhotoAsset[]; job?: PhotoJobSummary | null; }
export interface PhotoAssetContent { asset: PhotoAsset; data_base64: string; }
export interface PhotoCreateOptions { userContext?: string; manualObservation?: string; aiAssist?: boolean; sharedChildIds?: string[]; }
export interface BackupItem { archive: string; path: string; size_bytes: number; modified_at: string; }
export interface BackupCreateResult { archive: string; path: string; size_bytes: number; modified_at: string; manifest: { format_version: number; schema_version: number; created_at: string; record_count: number; asset_count: number; }; }
export interface BackupRestoreResult { archive: string; restored: boolean; rag_chunk_count: number; manifest: BackupCreateResult["manifest"]; }

export class CoreApiError extends Error {
  constructor(message: string) { super(message); this.name = "CoreApiError"; }
}

async function call<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  try { return await invoke<T>(command, args); }
  catch (error) { throw new CoreApiError(typeof error === "string" ? error : error instanceof Error ? error.message : "GrowWise Core 요청에 실패했습니다."); }
}

export const getHealth = () => call<HealthResponse>("core_health");
export const getCoreRuntimeStatus = () => call<CoreRuntimeStatus>("core_runtime_status");
export const createChild = (request: ChildCreateInput) => call<ChildProfile>("create_child", { request });
export const listChildren = () => call<ChildProfile[]>("list_children");
export const deleteChild = (childId: string) => call<ChildPurgeResult>("delete_child", { childId });
export const createObservation = (request: ObservationCreateInput) => call<LearningLog>("create_observation", { request });
export const listObservations = (childId: string) => call<LearningLog[]>("list_observations", { childId });
export const createActivity = (childId: string, title: string, sourceRefs: string[] = []) => call<ActivityPlan>("create_activity", { childId, title, sourceRefs });
export const listActivities = (childId: string) => call<ActivityPlan[]>("list_activities", { childId });
export const transitionActivity = (activityId: string, status: ActivityStatus, parentNote?: string) => call<ActivityPlan>("transition_activity", { activityId, status, parentNote: parentNote ?? null });
export const listActivityObservations = (activityId: string) => call<LearningLog[]>("list_activity_observations", { activityId });
export const searchChildContext = (childId: string, query: string) => call<SearchResponse>("search_child_context", { childId, query });
export const createConversation = (childId: string) => call<ConversationSession>("create_conversation", { childId });
export const listConversations = (childId: string) => call<ConversationSession[]>("list_conversations", { childId });
export const appendConversationTurn = (sessionId: string, question: string) => call<ConversationAnswer>("append_conversation_turn", { sessionId, question });
export const createResource = (request: ResourceCreateInput) => call<ResourceRecord>("create_resource", { request });
export const listResources = (childId?: string) => call<ResourceRecord[]>("list_resources", { childId: childId ?? null });
export const updateResource = (resourceId: string, request: ResourceCreateInput) => call<ResourceRecord>("update_resource", { resourceId, request });
export const deleteResource = (resourceId: string) => call<{ deleted: boolean }>("delete_resource", { resourceId });
export const generateMaterial = (childId: string, kind: MaterialKind, topic: string, goal?: string, sourceRefs: string[] = []) => call<GeneratedMaterial>("generate_material", { childId, kind, topic, goal: goal ?? null, sourceRefs });
export const listMaterials = (childId: string) => call<GeneratedMaterial[]>("list_materials", { childId });
export const reviewMaterial = (materialId: string, status: MaterialStatus, note?: string) => call<GeneratedMaterial>("review_material", { materialId, status, note: note ?? null });
export const reviseMaterial = (materialId: string, note?: string) => call<GeneratedMaterial>("revise_material", { materialId, note: note ?? null });
export const editMaterial = (materialId: string, title: string, contentMarkdown: string, note?: string | null) => call<GeneratedMaterial>("edit_material", { materialId, title, contentMarkdown, note: note ?? null });
export const getGrowthMap = (childId: string) => call<GrowthMap>("get_growth_map", { childId });
export const getInfantActivities = (childId: string) => call<InfantActivitySuggestions>("get_infant_activities", { childId });
export const getInfantObservationHints = (childId: string) => call<InfantObservationHints>("get_infant_observation_hints", { childId });
export const getBoardBookRecommendations = (childId: string) => call<BoardBookRecommendations>("get_board_book_recommendations", { childId });
export const createPhotoRecord = (
  childId: string,
  files: PhotoUploadInput[],
  options: PhotoCreateOptions = {},
) => call<PhotoDraftResult>("create_photo_record", {
  childId,
  files,
  userContext: options.userContext ?? null,
  manualObservation: options.manualObservation ?? null,
  aiAssist: options.aiAssist ?? true,
  sharedChildIds: options.sharedChildIds ?? [],
});
export const listPhotoRecords = (childId: string) => call<PhotoActivityRecord[]>("list_photo_records", { childId });
export const commitPhotoRecord = (recordId: string, observation?: string) => call<LearningLog>("commit_photo_record", { recordId, observation: observation ?? null });
export const getPhotoAsset = (childId: string, assetId: string) => call<PhotoAssetContent>("get_photo_asset", { childId, assetId });
export const listBackups = () => call<BackupItem[]>("list_backups");
export const createBackup = () => call<BackupCreateResult>("create_backup");
export const restoreBackup = (archiveName: string) => call<BackupRestoreResult>("restore_backup", { archiveName });
export const exportBackup = (archiveName: string) => call<string | null>("export_backup", { archiveName });
export const importBackup = () => call<(BackupRestoreResult & { safety_backup: string; imported_archive: string }) | null>("import_backup");
