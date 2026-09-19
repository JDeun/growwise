import "./HelpWorkspace.css";

const HELP_GROUPS = [
  {
    title: "GrowWise 시작하기",
    items: [
      ["첫 아이 등록", "아이 프로필에서 기본 정보를 등록하고 사진을 설정합니다."],
      ["기록 남기기", "학습 기록과 사진첩에서 일상의 배움과 활동을 남깁니다."],
      ["자료 만들기", "자료실에서 활동 자료를 만들고 부모 검토 후 사용합니다."],
    ],
  },
  {
    title: "데이터와 개인정보",
    items: [
      ["Local-first", "기록은 기본적으로 이 기기에 저장되고 백업도 사용자가 직접 관리합니다."],
      ["백업과 복원", "백업 및 복원에서 현재 데이터를 보관하거나 이전 백업으로 되돌릴 수 있습니다."],
      ["삭제", "설정에서 아이별 데이터를 영구 삭제할 수 있습니다."],
    ],
  },
  {
    title: "AI 사용 원칙",
    items: [
      ["보조 기능", "AI는 기록 정리, 검색과 자료 생성을 돕지만 필수 기능은 AI 없이도 동작합니다."],
      ["부모 검토", "생성된 자료와 사진 기록 초안은 부모 확인을 거쳐 최종 저장합니다."],
      ["근거 확인", "대화와 검색에서는 연결된 기록과 참고 자료를 함께 확인할 수 있습니다."],
    ],
  },
];

export function HelpWorkspace({ active }: { active: boolean }) {
  if (!active) return null;

  return (
    <section className="help-workspace" aria-labelledby="help-workspace-title">
      <header className="help-workspace-heading">
        <div>
          <p className="eyebrow">HELP & GUIDE</p>
          <h1 id="help-workspace-title">도움말</h1>
          <p>GrowWise의 주요 기능과 데이터 원칙을 빠르게 확인합니다.</p>
        </div>
        <span className="help-shortcut">⌘ / Ctrl + K · 대화하기</span>
      </header>

      <div className="help-grid">
        {HELP_GROUPS.map((group) => (
          <section className="help-card" key={group.title}>
            <h2>{group.title}</h2>
            <div className="help-items">
              {group.items.map(([title, description]) => (
                <article key={title}>
                  <strong>{title}</strong>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>

      <section className="help-support-card">
        <div>
          <span>문제가 있나요?</span>
          <strong>먼저 백업을 만든 뒤 앱 상태를 확인해 주세요.</strong>
          <p>설정의 앱 상태에서 Core와 AI 연결 정보를 확인할 수 있습니다.</p>
        </div>
      </section>
    </section>
  );
}
