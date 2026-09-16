import type { MaterialKind } from "./api";

export type MaterialPresentationLayout =
  | "activity"
  | "reading"
  | "language"
  | "math"
  | "science"
  | "writing"
  | "field-trip";

export interface MaterialPresentationTemplate {
  kind: MaterialKind;
  layout: MaterialPresentationLayout;
  label: string;
  purpose: string;
  zones: readonly [string, string, string];
}

const PRESENTATION_TEMPLATES: Record<MaterialKind, MaterialPresentationTemplate> = {
  activity_guide: {
    kind: "activity_guide",
    layout: "activity",
    label: "활동 실행 시트",
    purpose: "준비, 아이의 반응, 다음 연결을 한 장에서 정리합니다.",
    zones: ["준비·환경", "아이 반응·관찰", "다음 활동 연결"],
  },
  reading_activity: {
    kind: "reading_activity",
    layout: "reading",
    label: "읽기 대화 시트",
    purpose: "읽기 전 예상부터 읽은 뒤 대화와 생활 연결까지 기록합니다.",
    zones: ["읽기 전 예상", "기억에 남은 장면·말", "읽은 뒤 질문·생활 연결"],
  },
  english_card: {
    kind: "english_card",
    layout: "language",
    label: "영어 표현 카드 시트",
    purpose: "오늘 사용할 짧은 표현과 실제 반응, 다음 사용 장면을 남깁니다.",
    zones: ["오늘의 표현", "아이의 말·몸짓 반응", "다음에 써볼 상황"],
  },
  math_activity: {
    kind: "math_activity",
    layout: "math",
    label: "수학 탐구 시트",
    purpose: "생활 문제를 어떤 방법으로 풀었는지 과정과 설명을 기록합니다.",
    zones: ["문제 상황·실물", "아이의 방법", "다른 방법·설명"],
  },
  science_inquiry: {
    kind: "science_inquiry",
    layout: "science",
    label: "과학 탐구 시트",
    purpose: "정답보다 예측, 관찰, 결과 설명의 흐름을 남깁니다.",
    zones: ["예측", "관찰·실험", "결과·설명"],
  },
  writing_prompt: {
    kind: "writing_prompt",
    layout: "writing",
    label: "쓰기 초안 시트",
    purpose: "말과 그림으로 생각을 열고 초안과 다시 쓰기를 분리해 기록합니다.",
    zones: ["말·그림으로 생각 열기", "첫 초안", "다시 쓰고 돌아보기"],
  },
  field_trip: {
    kind: "field_trip",
    layout: "field-trip",
    label: "현장학습 기록 시트",
    purpose: "가기 전 궁금증, 현장 관찰, 돌아온 뒤 연결을 한 흐름으로 남깁니다.",
    zones: ["가기 전 궁금증", "현장 관찰·사진 메모", "돌아와서 연결"],
  },
};

export function materialPresentationTemplate(kind: MaterialKind): MaterialPresentationTemplate {
  return PRESENTATION_TEMPLATES[kind];
}
