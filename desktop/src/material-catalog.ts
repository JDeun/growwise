import type { MaterialKind, Stage } from "./api";

export interface MaterialCatalogItem {
  kind: MaterialKind;
  label: string;
  description: string;
  placeholder: string;
  goalPlaceholder: string;
  flow: readonly string[];
  reviewPoints: readonly string[];
}

export const MATERIAL_CATALOG: readonly MaterialCatalogItem[] = [
  {
    kind: "activity_guide",
    label: "활동 가이드",
    description: "일상 놀이와 관찰을 단계별로 연결합니다.",
    placeholder: "예: 비 오는 날 창밖 관찰",
    goalPlaceholder: "예: 정답보다 아이가 먼저 발견하고 반응할 시간을 충분히 주기",
    flow: ["준비", "함께 해 보기", "관찰 포인트", "다음 활동 연결"],
    reviewPoints: ["부모가 대신 수행하지 않는가", "관찰할 행동이 구체적인가"],
  },
  {
    kind: "reading_activity",
    label: "독서 활동지",
    description: "책을 읽기 전·중·후의 열린 질문과 확장 활동을 만듭니다.",
    placeholder: "예: 달팽이가 나오는 그림책",
    goalPlaceholder: "예: 내용 확인 문제보다 아이의 예측과 경험 연결을 중심으로",
    flow: ["읽기 전 관심 열기", "함께 읽으며 질문", "아이의 해석 듣기", "생활로 확장"],
    reviewPoints: ["정답형 독해 문제가 과하지 않은가", "책을 즐기는 흐름을 방해하지 않는가"],
  },
  {
    kind: "english_card",
    label: "영어 대화 카드",
    description: "짧은 상황 대화와 단계별 힌트를 준비합니다.",
    placeholder: "예: 카페에서 주문하기",
    goalPlaceholder: "예: 완벽한 문장보다 짧게라도 의미를 주고받는 경험 만들기",
    flow: ["상황 제시", "부모 모델링", "아이 차례", "단계별 힌트"],
    reviewPoints: ["표현 수가 부담스럽지 않은가", "한국어·몸짓 반응도 대화로 받아들이는가"],
  },
  {
    kind: "math_activity",
    label: "수학 놀이",
    description: "실물과 생활 맥락으로 수 개념을 탐색합니다.",
    placeholder: "예: 간식을 똑같이 나누기",
    goalPlaceholder: "예: 계산 답보다 아이가 물건을 옮기며 방법을 설명하게 하기",
    flow: ["생활 문제 만들기", "실물로 탐색", "힌트로 다시 시도", "방법 설명"],
    reviewPoints: ["정답을 바로 노출하지 않는가", "아이 손으로 조작할 수 있는가"],
  },
  {
    kind: "science_inquiry",
    label: "과학 탐구",
    description: "예측·관찰·비교·설명의 탐구 흐름을 만듭니다.",
    placeholder: "예: 비 오는 날의 달팽이",
    goalPlaceholder: "예: 사실 암기보다 먼저 예측하고 실제 관찰과 비교하게 하기",
    flow: ["궁금한 점", "예측", "관찰·실험", "비교·설명"],
    reviewPoints: ["직접 관찰 가능한가", "결론을 미리 정해 두지 않았는가"],
  },
  {
    kind: "writing_prompt",
    label: "글쓰기·말하기",
    description: "생각을 말·그림·글로 표현하도록 발판을 제공합니다.",
    placeholder: "예: 내가 만든 새로운 동물 이야기",
    goalPlaceholder: "예: 맞춤법 교정보다 아이가 자기 생각을 끝까지 표현하도록 돕기",
    flow: ["생각 열기", "말·그림으로 초안", "표현 확장", "돌아보기"],
    reviewPoints: ["모범 답안을 강요하지 않는가", "말·그림 등 여러 표현 방식을 허용하는가"],
  },
  {
    kind: "field_trip",
    label: "탐방·여행 활동지",
    description: "가기 전 질문, 현장 관찰, 돌아온 뒤 기록을 연결합니다.",
    placeholder: "예: 국립과천과학관",
    goalPlaceholder: "예: 체크리스트 완주보다 현장에서 아이가 궁금해한 한 가지를 깊게 보기",
    flow: ["가기 전 궁금증", "현장 관찰", "사진·메모", "돌아와 연결"],
    reviewPoints: ["현장 경험을 방해할 만큼 과하지 않은가", "사후 기록과 관찰이 연결되는가"],
  },
] as const;

const INFANT_KINDS = new Set<MaterialKind>([
  "activity_guide",
  "reading_activity",
  "english_card",
]);
const PRESCHOOL_KINDS = new Set<MaterialKind>(MATERIAL_CATALOG.map((item) => item.kind));

export function materialCatalogForStage(stage: Stage): MaterialCatalogItem[] {
  const allowed = stage === "infant_0_2" ? INFANT_KINDS : PRESCHOOL_KINDS;
  return MATERIAL_CATALOG.filter((item) => allowed.has(item.kind));
}

export function materialCatalogItem(kind: MaterialKind): MaterialCatalogItem {
  return MATERIAL_CATALOG.find((item) => item.kind === kind) ?? MATERIAL_CATALOG[0];
}
