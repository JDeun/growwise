import { invoke } from "@tauri-apps/api/core";

export type StudyProgressState = "planned" | "in_progress" | "review" | "revisit" | "comfortable";
export type MistakeType = "concept" | "process" | "reading" | "calculation" | "attention" | "communication" | "other";

export interface StudyUnitProgress {
  id: string;
  child_id: string;
  subject: string;
  unit: string;
  state: StudyProgressState;
  note: string | null;
  last_studied_at: string | null;
  created_at: string;
  updated_at: string;
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

export interface StudyWeakMap {
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
  status: "planned" | "done" | "skipped";
}

export interface StudyPlan {
  id: string;
  child_id: string;
  title: string;
  target_date: string | null;
  items: StudyPlanItem[];
  parent_note: string | null;
  created_at: string;
  updated_at: string;
}

async function invokeStudy<T>(command: string, args: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw new Error(
      typeof error === "string"
        ? error
        : error instanceof Error
          ? error.message
          : "학습 트래킹 요청에 실패했습니다.",
    );
  }
}

export const recordStudyProgress = (
  childId: string,
  request: {
    subject: string;
    unit: string;
    state: StudyProgressState;
    note: string | null;
    last_studied_at: string | null;
  },
) => invokeStudy<StudyUnitProgress>("record_study_progress", { childId, request });

export const recordStudyMistake = (
  childId: string,
  request: {
    subject: string;
    unit: string;
    mistake_type: MistakeType;
    prompt: string | null;
    learner_response: string | null;
    corrected_understanding: string | null;
    evidence_ref: string | null;
  },
) => invokeStudy("record_study_mistake", { childId, request });

export const recordStudyReflection = (
  childId: string,
  request: {
    subject: string;
    unit: string;
    worked_well: string | null;
    difficult_point: string | null;
    next_step: string | null;
  },
) => invokeStudy("record_study_reflection", { childId, request });

export const recordSelfExplanation = (
  childId: string,
  request: {
    subject: string;
    unit: string;
    explanation: string;
    evidence_refs: string[];
    open_question: string | null;
  },
) => invokeStudy("record_self_explanation", { childId, request });

export const getStudyWeakMap = (childId: string) =>
  invokeStudy<StudyWeakMap>("get_study_weak_map", { childId });

export const getStudyResources = (childId: string, subject: string, unit: string) =>
  invokeStudy<StudyResourceRecommendation[]>("get_study_resources", { childId, subject, unit });

export const createStudyPlan = (
  childId: string,
  request: { title: string; target_date: string | null; parent_note: string | null; max_items: number },
) => invokeStudy<StudyPlan>("create_study_plan", { childId, request });

export const listStudyPlans = (childId: string) =>
  invokeStudy<StudyPlan[]>("list_study_plans", { childId });
