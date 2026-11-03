import { invoke } from "@tauri-apps/api/core";

export const retryMaterialEnhancement = (materialId: string) =>
  invoke("retry_material_enhancement", { materialId });

import type { PhotoActivityRecord } from "./api";

export const deleteConversation = (sessionId: string) =>
  invoke<{ deleted: boolean }>("delete_conversation", { sessionId });

export const deleteEntityLink = (linkId: string, actingChildId: string) =>
  invoke<{ deleted: boolean }>("delete_entity_link", { linkId, actingChildId });

export const retryPhotoRecord = (recordId: string) =>
  invoke<{ record: PhotoActivityRecord }>("retry_photo_record", { recordId });
