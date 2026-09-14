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

export class CoreApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CoreApiError";
  }
}

export async function getHealth(): Promise<HealthResponse> {
  try {
    return await invoke<HealthResponse>("core_health");
  } catch (error) {
    throw new CoreApiError(
      typeof error === "string"
        ? error
        : error instanceof Error
          ? error.message
          : "GrowWise Core에 연결할 수 없습니다.",
    );
  }
}
