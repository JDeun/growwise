import { invoke } from "@tauri-apps/api/core";

export interface ConversationEvidence {
  source_id: string;
  entity_id: string;
  entity_type: string;
  title: string;
  occurred_at: string | null;
  body: string;
  source_url: string | null;
}

export const getConversationEvidence = (childId: string, sourceId: string) =>
  invoke<ConversationEvidence>("get_conversation_evidence", { childId, sourceId });
