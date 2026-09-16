import { invoke } from "@tauri-apps/api/core";

import { CoreApiError } from "./api";

export type StudyProgressState =
  | "planned"
  | "in_progress"
  | "review"
  | "revisit"
  | "comfortable";
export type MistakeType =
  | "concept"
  | "process"
  | "reading"
  | "calculation"
  | "attention"
  | "communication"
  | "other";
export type PlanItemStatus = "planned" | "done" | "skipped";

interface StudyEntityBase {
  id: string;
  child_id: string;
  created_at?: string;
  updated_at?: string;
}

export interface StudyUnitProgress extends StudyEntityBase {
  subject: string;
  unit: string;
  state: StudyProgressState;
  note: string | null;
  last_studied_at: string | null;
}

export interface MistakeRecord extends StudyEntityBase {
  subject: string;
  unit: string;
  mistake_type: MistakeType;
  prompt: string | null;
  learner_response: string | null;
  corrected_understanding: string | null;
  evidence_ref: string | null;
}

export interface StudyReflection extends StudyEntityBase {
  subject: string;
  unit: string;
  worked_well: string | null;
  difficult_point: string | null;
  next_step: string | null;
}

export interface SelfExplanationLog extends StudyEntityBase {
  subject: string;
  unit: string;
  explanation: string;
  evidence_refs: string[];
  open_question: string | null;
}

export interface WeakMapEntry {
  subject: string;
  unit: string;
  evidence_count: number;
  recurring_mistake_types: string[];
  recent_difficulties: string[];
  progress_state: StudyProgressState | null;
  parent_support_points: string[];
}

export interface WeakMap {
  child_id: string;
  entries: WeakMapEntry[];
  peer_comparison_used: false;
  interpretation: string;
}

export interface StudyResourceRecommendation {
  resource_id: string;
  title: string;
  reason: string;
  source_ref: string;
}

export interface StudyPlanItem {
  subject: string;
  unit: string;
  focus: string;
  status: PlanItemStatus;
}

export interface StudyPlan extends StudyEntityBase {
  title: string;
  target_date: string | null;
  items: StudyPlanItem[];
  parent_note: string | null;
}

export interface StudyProgressInput {
  subject: string;
  unit: string;
  state: StudyProgressState;
  note?: string | null;
  last_studied_at?: string | null;
}

export interface StudyMistakeInput {
  subject: string;
  unit: string;
  mistake_type: MistakeType;
  prompt?: string | null;
  learner_response?: string | null;
  corrected_understanding?: string | null;
  evidence_ref?: string | null;
}

export interface StudyReflectionInput {
  subject: string;
  unit: string;
  worked_well?: string | null;
  difficult_point?: string | null;
  next_step?: string | null;
}

export interface SelfExplanationInput {
  subject: string;
  unit: string;
  explanation: string;
  evidence_refs?: string[];
  open_question?: string | null;
}

export interface StudyPlanInput {
  title: string;
  target_date?: string | null;
  parent_note?: string | null;
  max_items?: number;
}

async function callStudy<T>(command: string, args: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw new CoreApiError(
      typeof error === "string"
        ? error
        : error instanceof Error
          ? error.message
          : "중·고 학습 추적 요청에 실패했습니다.",
    );
  }
}

export const recordStudyProgress = (childId: string, request: StudyProgressInput) =>
  callStudy<StudyUnitProgress>("record_study_progress", { childId, request });
export const listStudyProgress = (childId: string) =>
  callStudy<StudyUnitProgress[]>("list_study_progress", { childId });

export const recordStudyMistake = (childId: string, request: StudyMistakeInput) =>
  callStudy<MistakeRecord>("record_study_mistake", { childId, request });
export const listStudyMistakes = (childId: string) =>
  callStudy<MistakeRecord[]>("list_study_mistakes", { childId });

export const recordStudyReflection = (childId: string, request: StudyReflectionInput) =>
  callStudy<StudyReflection>("record_study_reflection", { childId, request });
export const listStudyReflections = (childId: string) =>
  callStudy<StudyReflection[]>("list_study_reflections", { childId });

export const recordSelfExplanation = (childId: string, request: SelfExplanationInput) =>
  callStudy<SelfExplanationLog>("record_self_explanation", { childId, request });
export const listSelfExplanations = (childId: string) =>
  callStudy<SelfExplanationLog[]>("list_self_explanations", { childId });

export const getStudyWeakMap = (childId: string) =>
  callStudy<WeakMap>("get_study_weak_map", { childId });
export const recommendStudyResources = (childId: string, subject: string, unit: string) =>
  callStudy<StudyResourceRecommendation[]>("recommend_study_resources", {
    childId,
    subject,
    unit,
  });

export const createStudyPlan = (childId: string, request: StudyPlanInput) =>
  callStudy<StudyPlan>("create_study_plan", { childId, request });
export const listStudyPlans = (childId: string) =>
  callStudy<StudyPlan[]>("list_study_plans", { childId });
export const updateStudyPlanItemStatus = (
  childId: string,
  planId: string,
  itemIndex: number,
  status: PlanItemStatus,
) =>
  callStudy<StudyPlan>("update_study_plan_item_status", {
    childId,
    planId,
    itemIndex,
    status,
  });
