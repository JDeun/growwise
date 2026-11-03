import { invoke } from "@tauri-apps/api/core";

export interface LearningWiki {
  id: string;
  child_id: string;
  title: string;
  content_markdown: string;
  source_refs: string[];
  revision: number;
  rebuilt_at: string;
  generator_mode: string;
  derived: true;
}

export const getLearningWiki = (childId: string) =>
  invoke<LearningWiki>("get_learning_wiki", { childId });

export const rebuildLearningWiki = (childId: string) =>
  invoke<LearningWiki>("rebuild_learning_wiki", { childId });
