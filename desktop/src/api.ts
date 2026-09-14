import { invoke } from "@tauri-apps/api/core";

export type OperationMode = "ai_enhanced_with_core_fallback" | "core_only";
export type ExperienceAxis = "physical" | "emotional_character" | "expression_art" | "thinking_inquiry" | "social" | "reading" | "speaking" | "writing" | "math" | "exploration";
export type ResourceKind = "book" | "curriculum" | "web" | "note" | "file";
export type MaterialKind = "activity_guide" | "reading_activity" | "english_card" | "math_activity" | "science_inquiry" | "writing_prompt" | "field_trip";
export type MaterialStatus = "draft" | "review_pending" | "revision_requested" | "approved" | "rejected" | "archived";

export interface HealthResponse { status: string; operation_mode: OperationMode; core_requires_llm: boolean; llm_features_enabled: boolean; embedding_features_enabled: boolean; model_provider: string; }
export interface CoreRuntimeStatus { started_by_desktop: boolean; }
export interface ChildCreateInput { nickname: string; stage: "infant_0_2" | "preschool_3_5" | "elementary" | "middle" | "high"; age_months: number | null; interests: string[]; }
export interface ChildProfile { id: string; nickname: string; stage: string; age_months: number | null; interests: string[]; }
export interface ObservationCreateInput { child_id: string; observation: string; experience_axes: ExperienceAxis[]; }
export interface LearningLog { id: string; child_id: string; parent_observation: string; tags: string[]; experience_axes: ExperienceAxis[]; interest: string | null; next_activity: string | null; created_at: string | null; }
export interface GrowthMap { child_id: string; period_days: number; total_logs_in_period: number; tagged_logs_in_period: number; axes: Array<{ axis: ExperienceAxis; state: string; observation_count: number; }>; }
export interface ActivitySuggestion { title: string; description: string; materials: string[]; observation_cue: string | null; tags: string[]; }
export interface InfantActivitySuggestions { suggestions: ActivitySuggestion[]; }
export interface SearchPlan { keywords: string[]; entity_types: string[]; limit: number; }
export interface SearchResponse { query: string; plan: SearchPlan; results: Array<Record<string, unknown>>; }
export interface ConversationSession { id: string; child_id: string; title: string | null; turns: Array<{ role: "user" | "assistant"; content: string; source_ids: string[]; created_at: string; }>; }
export interface ConversationAnswer { session_id: string; thread_id: string; answer: { answer: string; source_ids: string[]; insufficient_evidence: boolean; }; turn_count: number; }
export interface ResourceCreateInput { kind: ResourceKind; title: string; child_id: string | null; summary: string | null; content: string | null; source_url: string | null; source_name: string | null; author: string | null; tags: string[]; stage_tags: string[]; provenance: Record<string, string>; }
export interface ResourceRecord extends ResourceCreateInput { id: string; created_at?: string; updated_at?: string; }
export interface GeneratedMaterial { id: string; child_id: string; kind: MaterialKind; title: string; content_markdown: string; status: MaterialStatus; source_refs: string[]; generator_mode: string; review_note: string | null; created_at?: string; updated_at?: string; }

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
export const createObservation = (request: ObservationCreateInput) => call<LearningLog>("create_observation", { request });
export const listObservations = (childId: string) => call<LearningLog[]>("list_observations", { childId });
export const searchChildContext = (childId: string, query: string) => call<SearchResponse>("search_child_context", { childId, query });
export const createConversation = (childId: string) => call<ConversationSession>("create_conversation", { childId });
export const appendConversationTurn = (sessionId: string, question: string) => call<ConversationAnswer>("append_conversation_turn", { sessionId, question });
export const createResource = (request: ResourceCreateInput) => call<ResourceRecord>("create_resource", { request });
export const listResources = (childId?: string) => call<ResourceRecord[]>("list_resources", { childId: childId ?? null });
export const generateMaterial = (childId: string, kind: MaterialKind, topic: string, goal?: string, sourceRefs: string[] = []) => call<GeneratedMaterial>("generate_material", { childId, kind, topic, goal: goal ?? null, sourceRefs });
export const listMaterials = (childId: string) => call<GeneratedMaterial[]>("list_materials", { childId });
export const reviewMaterial = (materialId: string, status: MaterialStatus, note?: string) => call<GeneratedMaterial>("review_material", { materialId, status, note: note ?? null });
export const getGrowthMap = (childId: string) => call<GrowthMap>("get_growth_map", { childId });
export const getInfantActivities = (childId: string) => call<InfantActivitySuggestions>("get_infant_activities", { childId });
