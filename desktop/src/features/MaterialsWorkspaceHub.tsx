import { useState, type ReactNode } from "react";

import "./MaterialsWorkspaceHub.css";

type MaterialTab = "materials" | "library" | "discovery";

interface MaterialsWorkspaceHubProps {
  app: ReactNode;
  renderDiscovery: (active: boolean) => ReactNode;
}

const TABS: Array<{ value: MaterialTab; label: string; description: string }> = [
  { value: "materials", label: "활동 자료", description: "만들기 · 검토 · 승인" },
  { value: "library", label: "참고 자료", description: "내 자료와 출처" },
  { value: "discovery", label: "자료 찾기", description: "책 · 교육과정 · 탐방" },
];

export function MaterialsWorkspaceHub({ app, renderDiscovery }: MaterialsWorkspaceHubProps) {
  const [tab, setTab] = useState<MaterialTab>("materials");

  return (
    <section className="materials-hub" data-material-tab={tab} aria-labelledby="materials-hub-title">
      <header className="materials-hub-heading">
        <div>
          <p className="eyebrow">LEARNING MATERIALS</p>
          <h1 id="materials-hub-title">자료실</h1>
          <p>아이에게 필요한 활동 자료를 만들고, 참고 자료와 외부 자료를 한곳에서 관리합니다.</p>
        </div>
      </header>

      <div className="materials-hub-tabs" role="tablist" aria-label="자료실 보기">
        {TABS.map((item) => (
          <button
            type="button"
            role="tab"
            aria-selected={tab === item.value}
            className={tab === item.value ? "is-active" : ""}
            key={item.value}
            onClick={() => setTab(item.value)}
          >
            <strong>{item.label}</strong>
            <small>{item.description}</small>
          </button>
        ))}
      </div>

      <div className="materials-hub-core">{app}</div>
      <div className="materials-hub-discovery">{renderDiscovery(tab === "discovery")}</div>
    </section>
  );
}
