import type { WorkspaceView } from "./workspaceTypes";

export const WORKSPACE_DESCRIPTIONS: Record<WorkspaceView, string> = {
  home: "아이별 현황, 최근 기록, 오늘의 제안과 백업 상태를 한눈에 봅니다.",
  observations: "프로필과 관찰 기록을 한 화면에서 관리합니다.",
  learning: "독서·일기·학교·학원·자율학습 기록을 모아봅니다.",
  materials: "근거 자료로 AI 학습자료를 만들고 검토·승인합니다.",
  photos: "사진과 메모로 활동 기록을 남기고 검토합니다.",
  search: "쌓인 기록을 검색하고 근거 기반 대화를 이어갑니다.",
  library: "채택한 책·메모·웹 자료와 출처를 관리합니다.",
  growth: "최근 경험과 기록의 흐름을 살펴봅니다.",
  activities: "추천 활동과 진행 상태를 관리합니다.",
  discovery: "책·교육과정·탐방 후보를 찾아봅니다.",
  settings: "백업·복원, 아이 프로필 상세, AI와 앱 상태를 관리합니다.",
};
