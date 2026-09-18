import type { WorkspaceView } from "./workspaceTypes";

export const WORKSPACE_DESCRIPTIONS: Record<WorkspaceView, string> = {
  home: "현재 아이와 다음 할 일을 한눈에 봅니다.",
  profile: "아이 정보와 성장 맥락을 한곳에서 관리합니다.",
  observations: "일상에서 의미 있었던 순간을 기록합니다.",
  photos: "사진과 메모로 활동 기록을 남깁니다.",
  learning: "독서·일기·학교·학원·자율학습을 따로 기록합니다.",
  growth: "최근 경험과 기록의 흐름을 살펴봅니다.",
  activities: "할 활동을 고르고 진행 상태를 관리합니다.",
  search: "기록을 검색하고 근거가 연결된 대화를 이어갑니다.",
  discovery: "책·교육과정·탐방 후보를 찾아봅니다.",
  library: "채택해 둔 책·메모·웹 자료와 출처를 관리합니다.",
  materials: "저장한 근거로 학습 자료를 만들고 검토합니다.",
  settings: "백업·복원과 앱 상태, 개인정보 설정을 관리합니다.",
};
