import { invoke } from "@tauri-apps/api/core";

export type LocalModelComponent = "text" | "vision" | "embedding";

export interface InstalledLocalModel {
  name: string;
  size: number;
  digest: string;
  modified_at?: string | null;
}

export const listLocalModels = (component: LocalModelComponent) =>
  invoke<InstalledLocalModel[]>("list_local_models", { component });

export const removeLocalModel = (component: LocalModelComponent, model: string) =>
  invoke<void>("remove_local_model", { component, model, confirmed: true });

export const setLocalModel = (component: LocalModelComponent, model: string) =>
  invoke<void>("set_local_model", { component, model });
