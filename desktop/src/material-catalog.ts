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

const INFANT_OVERRIDES: Partial<Record<MaterialKind, Partial<MaterialCatalogItem>>> = {
  activity_guide: {
    description: "부모와 함께하는 짧은 감각 놀이와 반응 관찰을 준비합니다.",
    placeholder: "예: 부드러운 천 만져보기",
    goalPlaceholder: "예: 결과를 요구하지 않고 아이가 오래 머무는 감각과 움직임 관찰하기",
    flow: ["안전한 준비", "함께 놀이", "아이 반응 따라가기", "부모 메모"],
    reviewPoints: ["수행을 요구하지 않는가", "안전하고 짧은 상호작용인가"],
  },
  reading_activity: {
    label: "보드북 함께 보기",
    description: "큰 그림과 소리를 함께 보며 아이의 시선·몸짓·소리 반응을 따라갑니다.",
    placeholder: "예: 고양이가 나오는 보드북",
    goalPlaceholder: "예: 끝까지 읽기보다 아이가 오래 보는 그림에서 멈추고 주고받기",
    flow: ["책 준비", "함께 보기", "소리·몸짓 주고받기", "부모 메모"],
    reviewPoints: ["대답을 요구하지 않는가", "아이가 고른 페이지와 반응을 따라가는가"],
  },
  english_card: {
    label: "영어 소리 놀이",
    description: "아주 짧은 영어 소리와 몸짓을 부모가 모델링하며 주고받습니다.",
    placeholder: "예: hello 인사 놀이",
    goalPlaceholder: "예: 발음을 가르치기보다 표정·소리·몸짓으로 즐겁게 주고받기",
    flow: ["짧은 표현 고르기", "부모 모델링", "반응 기다리기", "부모 메모"],
    reviewPoints: ["정확한 발음을 요구하지 않는가", "옹알이·몸짓도 반응으로 받아들이는가"],
  },
  math_activity: {
    label: "수·크기 감각 놀이",
    description: "세기·모으기·크기 차이를 실물 놀이로 경험하고 부모가 반응을 관찰합니다.",
    placeholder: "예: 블록 하나씩 건네기",
    goalPlaceholder: "예: 수를 맞히게 하지 않고 물건을 모으고 나누는 방식 관찰하기",
    flow: ["안전한 실물 준비", "함께 세기·비교", "자유롭게 옮기기", "부모 메모"],
    reviewPoints: ["수를 맞히게 하지 않는가", "손으로 자유롭게 탐색할 수 있는가"],
  },
  science_inquiry: {
    label: "감각 탐색",
    description: "안전한 사물의 소리·감촉·움직임을 함께 살피며 호기심을 따라갑니다.",
    placeholder: "예: 물이 흔들리는 모습 보기",
    goalPlaceholder: "예: 설명을 가르치기보다 아이가 반복해서 만지고 바라보는 변화 관찰하기",
    flow: ["안전한 대상 준비", "감각으로 살피기", "반응 따라가기", "부모 메모"],
    reviewPoints: ["안전하게 직접 탐색 가능한가", "결론이나 정답을 요구하지 않는가"],
  },
  writing_prompt: {
    label: "끼적이기·소리 표현",
    description: "말 이전의 몸짓·옹알이·끼적이기를 아이의 표현으로 받아 기록합니다.",
    placeholder: "예: 큰 종이에 크레용 끼적이기",
    goalPlaceholder: "예: 잘 그리거나 말하게 하지 않고 반복하는 선·색·소리 관찰하기",
    flow: ["표현 재료 준비", "자유롭게 표현", "부모가 말로 담아주기", "부모 메모"],
    reviewPoints: ["결과물을 요구하지 않는가", "몸짓·소리·끼적이기를 표현으로 존중하는가"],
  },
  field_trip: {
    label: "짧은 나들이 기록",
    description: "가까운 장소에서 아이가 바라보고 듣는 것에 머물며 부모가 관찰을 남깁니다.",
    placeholder: "예: 집 앞 공원 나들이",
    goalPlaceholder: "예: 일정을 채우기보다 아이가 멈추는 풍경과 소리에 충분히 머물기",
    flow: ["가까운 장소 고르기", "천천히 함께 보기", "아이 반응 따라가기", "부모 메모"],
    reviewPoints: ["일정이 아이에게 과하지 않은가", "아이의 휴식과 반응을 우선하는가"],
  },
};

export function materialCatalogForStage(stage: Stage): MaterialCatalogItem[] {
  if (stage !== "infant_0_2") return [...MATERIAL_CATALOG];
  return MATERIAL_CATALOG.map((item) => ({
    ...item,
    ...INFANT_OVERRIDES[item.kind],
    kind: item.kind,
  }));
}

export function materialCatalogItem(kind: MaterialKind): MaterialCatalogItem {
  return MATERIAL_CATALOG.find((item) => item.kind === kind) ?? MATERIAL_CATALOG[0];
}
