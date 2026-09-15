import type { MaterialKind, Stage } from "./api";

export interface MaterialCatalogItem {
  kind: MaterialKind;
  label: string;
  description: string;
  placeholder: string;
}

export const MATERIAL_CATALOG: readonly MaterialCatalogItem[] = [
  { kind: "activity_guide", label: "활동 가이드", description: "일상 놀이와 관찰을 단계별로 연결합니다.", placeholder: "예: 비 오는 날 창밖 관찰" },
  { kind: "reading_activity", label: "독서 활동지", description: "책을 읽기 전·중·후의 열린 질문과 확장 활동을 만듭니다.", placeholder: "예: 달팽이가 나오는 그림책" },
  { kind: "english_card", label: "영어 대화 카드", description: "짧은 상황 대화와 단계별 힌트를 준비합니다.", placeholder: "예: 카페에서 주문하기" },
  { kind: "field_trip", label: "탐방·여행 활동지", description: "가기 전 질문, 현장 관찰, 돌아온 뒤 기록을 연결합니다.", placeholder: "예: 국립과천과학관" },
  { kind: "math_activity", label: "수학 놀이", description: "실물과 생활 맥락으로 수 개념을 탐색합니다.", placeholder: "예: 간식을 똑같이 나누기" },
  { kind: "science_inquiry", label: "과학 탐구", description: "예측·관찰·비교·설명의 탐구 흐름을 만듭니다.", placeholder: "예: 얼음은 어디에서 빨리 녹을까" },
  { kind: "writing_prompt", label: "글쓰기·말하기", description: "생각을 말·그림·글로 표현하도록 발판을 제공합니다.", placeholder: "예: 내가 만든 새로운 동물 이야기" },
] as const;

const INFANT_KINDS = new Set<MaterialKind>(["activity_guide", "reading_activity", "english_card"]);
const PRESCHOOL_KINDS = new Set<MaterialKind>(["activity_guide", "reading_activity", "english_card", "field_trip", "math_activity", "science_inquiry", "writing_prompt"]);

export function materialCatalogForStage(stage: Stage): MaterialCatalogItem[] {
  const allowed = stage === "infant_0_2" ? INFANT_KINDS : PRESCHOOL_KINDS;
  return MATERIAL_CATALOG.filter((item) => allowed.has(item.kind));
}

export function materialCatalogItem(kind: MaterialKind): MaterialCatalogItem {
  return MATERIAL_CATALOG.find((item) => item.kind === kind) ?? MATERIAL_CATALOG[0];
}
