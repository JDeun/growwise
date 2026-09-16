import { invoke } from "@tauri-apps/api/core";

import type { ResourceKind, ResourceRecord } from "./api";

export type DiscoveryCategory = "book" | "curriculum" | "place";

export interface DiscoverySuggestion {
  candidate_id: string;
  category: DiscoveryCategory;
  resource_kind: ResourceKind;
  title: string;
  summary: string | null;
  source_name: string;
  source_url: string | null;
  author: string | null;
  attribution: string;
  license_note: string;
  cache_status: string;
  rationale: string;
  query_term: string | null;
  tags: string[];
  metadata: Record<string, string>;
}

export interface DiscoverySourceState {
  source: string;
  enabled: boolean;
  status: string;
  detail: string | null;
}

export interface DiscoveryResponse {
  query: string;
  query_terms: string[];
  suggestions: DiscoverySuggestion[];
  sources: DiscoverySourceState[];
}

export async function discoverEducationResources(
  childId: string,
  query?: string,
): Promise<DiscoveryResponse> {
  return invoke<DiscoveryResponse>("discover_education_resources", {
    childId,
    query: query?.trim() || null,
  });
}

export async function saveDiscoveredResource(
  childId: string,
  suggestion: DiscoverySuggestion,
): Promise<ResourceRecord> {
  return invoke<ResourceRecord>("save_discovered_resource", {
    childId,
    suggestion,
  });
}
