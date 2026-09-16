import type { WorkspaceView } from "./workspaceTypes";

export const WORKSPACE_DESCRIPTIONS: Record<WorkspaceView, string> = {
  home: "아이 프로필과 현재 맥락을 확인합니다.",
  observations: "의미 있는 관찰과 타임라인을 기록합니다.",
  photos: "사진과 부모 기록으로 활동 일기를 남깁니다.",
  learning: "독서·일기·학교·학원·자율학습처럼 별도로 한 학습을 기록합니다.",
  growth: "최근 경험 축과 성장 맥락을 살펴봅니다.",
  activities: "활동을 제안하고 진행 상태를 관리합니다.",
  search: "아이의 기록과 후속 질문을 탐색합니다.",
  discovery: "아이 맥락과 공개 교육 자원에서 책·교육과정·탐방 후보를 찾습니다.",
  library: "부모가 채택한 참고 자료와 근거를 관리합니다.",
  materials: "채택한 근거와 아이 맥락을 바탕으로 자료를 만들고 검토합니다.",
  settings: "백업과 로컬 운영 설정을 관리합니다.",
};
