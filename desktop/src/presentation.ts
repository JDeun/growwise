import type { ActivityStatus, ExperienceAxis, GrowthMap, Stage } from "./api";

export const AXIS_OPTIONS: Array<{ value: ExperienceAxis; label: string }> = [
  { value: "physical", label: "신체" },
  { value: "emotional_character", label: "정서·인성" },
  { value: "expression_art", label: "표현·예술" },
  { value: "thinking_inquiry", label: "사고·탐구" },
  { value: "social", label: "사회성" },
  { value: "reading", label: "읽기" },
  { value: "speaking", label: "말하기" },
  { value: "writing", label: "쓰기" },
  { value: "math", label: "수학" },
  { value: "exploration", label: "탐색" },
];

export function resultText(result: Record<string, unknown>): string {
  if (typeof result.parent_observation === "string") return result.parent_observation;
  if (typeof result.title === "string") return result.title;
  return "관련 기록";
}

export function stageLabel(stage: Stage): string {
  return {
    infant_0_2: "영아 0~2세",
    preschool_3_5: "유아 3~5세",
    elementary: "초등",
    middle: "중등",
    high: "고등",
  }[stage];
}

export function diversityLabel(state: GrowthMap["diversity"]["state"]): string {
  return {
    insufficient_data: "판단 보류",
    varied: "여러 경험이 관찰됨",
    mixed: "여러 경험과 반복이 함께 관찰됨",
    concentrated: "일부 경험이 자주 기록됨",
  }[state];
}

export function axisLabel(axis: ExperienceAxis): string {
  return AXIS_OPTIONS.find((item) => item.value === axis)?.label ?? axis;
}

export function activityStatusLabel(status: ActivityStatus): string {
  return {
    suggested: "제안됨",
    active: "진행 중",
    completed: "완료",
    skipped: "건너뜀",
    archived: "보관됨",
  }[status];
}
