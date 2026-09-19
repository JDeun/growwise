import { invoke } from "@tauri-apps/api/core";

import type { ResourceKind, ResourceRecord } from "./api";

export type DiscoveryCategory =
  | "book"
  | "curriculum"
  | "place"
  | "reference"
  | "science"
  | "nature"
  | "media";

export interface DiscoverySuggestion {
  candidate_id: string;
  category: DiscoveryCategory;
  resource_kind: ResourceKind;
  title: string;
  summary: string | null;
  content: string | null;
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

export interface DiscoveryLocation {
  latitude: number;
  longitude: number;
}

export function parseDiscoveryLocation(
  latitudeText: string,
  longitudeText: string,
): DiscoveryLocation | null {
  const latitudeValue = latitudeText.trim();
  const longitudeValue = longitudeText.trim();
  if (!latitudeValue && !longitudeValue) return null;
  if (!latitudeValue || !longitudeValue) {
    throw new Error("탐방 위치의 위도와 경도는 함께 입력해 주세요.");
  }
  const latitude = Number(latitudeValue);
  const longitude = Number(longitudeValue);
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
    throw new Error("위도는 -90에서 90 사이의 숫자로 입력해 주세요.");
  }
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    throw new Error("경도는 -180에서 180 사이의 숫자로 입력해 주세요.");
  }
  return { latitude, longitude };
}

export async function discoverEducationResources(
  childId: string,
  query?: string,
  location?: DiscoveryLocation | null,
): Promise<DiscoveryResponse> {
  return invoke<DiscoveryResponse>("discover_education_resources", {
    childId,
    query: query?.trim() || null,
    latitude: location?.latitude ?? null,
    longitude: location?.longitude ?? null,
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
