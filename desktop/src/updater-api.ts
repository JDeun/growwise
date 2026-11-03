import { invoke } from "@tauri-apps/api/core";

export interface AppUpdateStatus {
  configured: boolean;
  current_version: string;
  checked: boolean;
  available_version: string | null;
  notes: string | null;
}

export const appUpdateStatus = () => invoke<AppUpdateStatus>("app_update_status");
export const checkAppUpdate = () => invoke<AppUpdateStatus>("check_app_update");
export const installAppUpdate = (version: string) =>
  invoke<void>("install_app_update", { version, confirmed: true });
