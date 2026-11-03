import { invoke } from "@tauri-apps/api/core";

export const API_KEY_SERVICES = [
  { id: "data4library", label: "도서관 정보나루" },
  { id: "google_books", label: "Google Books" },
  { id: "national_library", label: "국립중앙도서관 ISBN" },
  { id: "krdict", label: "한국어기초사전" },
  { id: "data_go_kr", label: "공공데이터포털" },
  { id: "model", label: "원격 호환 AI · 고급 설정" },
] as const;

export type ApiServiceId = typeof API_KEY_SERVICES[number]["id"];
export interface ApiCredentialStatus {
  service_id: ApiServiceId;
  configured: boolean;
  source: "saved" | "environment" | "disabled" | "none";
  supported: boolean;
}
export interface ApiCredentialConnection {
  service: ApiServiceId;
  status: "available" | "reachable_no_results" | "missing_key" | "unavailable";
  message: string;
}

export const listApiCredentials = () => invoke<ApiCredentialStatus[]>("list_api_credentials");
export const saveApiCredential = (serviceId: ApiServiceId, value: string) =>
  invoke<void>("save_api_credential", { serviceId, value });
export const deleteApiCredential = (serviceId: ApiServiceId) =>
  invoke<void>("delete_api_credential", { serviceId });
export const testApiCredential = (serviceId: ApiServiceId) =>
  invoke<ApiCredentialConnection>("test_api_credential", { serviceId });
