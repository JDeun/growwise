import type { GeneratedMaterial, MaterialKind, MaterialStatus } from "./api";

export const MATERIAL_KIND_LABELS: Record<MaterialKind, string> = {
  activity_guide: "활동 가이드",
  reading_activity: "독서 활동지",
  english_card: "영어 대화 카드",
  math_activity: "수학 놀이",
  science_inquiry: "과학 탐구",
  writing_prompt: "글쓰기·말하기",
  field_trip: "탐방·여행 활동지",
};

export const MATERIAL_STATUS_LABELS: Record<MaterialStatus, string> = {
  draft: "초안",
  review_pending: "부모 검토 필요",
  revision_requested: "수정 요청됨",
  approved: "승인됨",
  rejected: "사용 안 함",
  archived: "보관됨",
};

export type MaterialLane = "review" | "approved" | "inactive";

export function materialLane(status: MaterialStatus): MaterialLane {
  if (status === "approved") return "approved";
  if (status === "rejected" || status === "archived") return "inactive";
  return "review";
}

export function canPrintMaterial(material: GeneratedMaterial): boolean {
  return material.status === "approved";
}

export function groupMaterials(materials: GeneratedMaterial[]) {
  return materials.reduce<Record<MaterialLane, GeneratedMaterial[]>>(
    (groups, material) => {
      groups[materialLane(material.status)].push(material);
      return groups;
    },
    { review: [], approved: [], inactive: [] },
  );
}
