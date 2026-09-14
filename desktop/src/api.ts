import { invoke } from "@tauri-apps/api/core";

export type OperationMode = "ai_enhanced_with_core_fallback" | "core_only";

export interface HealthResponse {
  status: string;
  operation_mode: OperationMode;
  core_requires_llm: boolean;
  llm_features_enabled: boolean;
  embedding_features_enabled: boolean;
  model_provider: string;
}

export interface CoreRuntimeStatus {
  started_by_desktop: boolean;
}

export interface ChildCreateInput {
  nickname: string;
  stage: "infant_0_2" | "preschool_3_5" | "elementary" | "middle" | "high";
  age_months: number | null;
  interests: string[];
}

export interface ChildProfile {
  id: string;
  nickname: string;
  stage: string;
  age_months: number | null;
  interests: string[];
}

export interface GrowthMap {
  child_id: string;
  period_days: number;
  total_logs_in_period: number;
  tagged_logs_in_period: number;
  axes: Array<{
    axis: string;
    state: string;
    observation_count: number;
  }>;
}

export class CoreApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CoreApiError";
  }
}

async function call<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw new CoreApiError(
      typeof error === "string"
        ? error
        : error instanceof Error
          ? error.message
          : "GrowWise Core 요청에 실패했습니다.",
    );
  }
}

export function getHealth(): Promise<HealthResponse> {
  return call<HealthResponse>("core_health");
}

export function getCoreRuntimeStatus(): Promise<CoreRuntimeStatus> {
  return call<CoreRuntimeStatus>("core_runtime_status");
}

export function createChild(request: ChildCreateInput): Promise<ChildProfile> {
  return call<ChildProfile>("create_child", { request });
}

export function getGrowthMap(childId: string): Promise<GrowthMap> {
  return call<GrowthMap>("get_growth_map", { childId });
}
