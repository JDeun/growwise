export type OperationMode = "ai_enhanced_with_core_fallback" | "core_only";

export interface HealthResponse {
  status: string;
  operation_mode: OperationMode;
  core_requires_llm: boolean;
  llm_features_enabled: boolean;
  embedding_features_enabled: boolean;
  model_provider: string;
}

const CORE_BASE_URL = import.meta.env.VITE_GROWWISE_CORE_URL ?? "http://127.0.0.1:8765";

export class CoreApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "CoreApiError";
  }
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  let response: Response;
  try {
    response = await fetch(`${CORE_BASE_URL}/health`, { signal });
  } catch (error) {
    throw new CoreApiError(
      error instanceof Error ? error.message : "GrowWise Core에 연결할 수 없습니다.",
    );
  }

  if (!response.ok) {
    throw new CoreApiError(`GrowWise Core health check 실패 (${response.status})`, response.status);
  }
  return (await response.json()) as HealthResponse;
}
