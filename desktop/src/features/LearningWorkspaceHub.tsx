import { useState, type ReactNode } from "react";

import "./LearningWorkspaceHub.css";

type LearningTab = "records" | "observations";

interface LearningWorkspaceHubProps {
  renderRecords: (active: boolean) => ReactNode;
  observationApp: ReactNode;
}

export function LearningWorkspaceHub({
  renderRecords,
  observationApp,
}: LearningWorkspaceHubProps) {
  const [tab, setTab] = useState<LearningTab>("records");

  return (
    <section
      className="learning-hub"
      data-learning-tab={tab}
      aria-labelledby="learning-hub-title"
    >
      <header className="learning-hub-heading">
        <div>
          <p className="eyebrow">LEARNING RECORDS</p>
          <h1 id="learning-hub-title">학습 기록</h1>
          <p>배움의 결과와 일상의 관찰을 같은 기록 흐름 안에서 관리합니다.</p>
        </div>
      </header>

      <div className="learning-hub-tabs" role="tablist" aria-label="학습 기록 보기">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "records"}
          className={tab === "records" ? "is-active" : ""}
          onClick={() => setTab("records")}
        >
          <strong>학습 기록</strong>
          <small>독서 · 학교 · 자율학습 · 과제</small>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "observations"}
          className={tab === "observations" ? "is-active" : ""}
          onClick={() => setTab("observations")}
        >
          <strong>관찰 기록</strong>
          <small>일상의 발견 · 경험 축 · 타임라인</small>
        </button>
      </div>

      <div className="learning-hub-records">
        {renderRecords(tab === "records")}
      </div>
      <div className="learning-hub-observations">
        {observationApp}
      </div>
    </section>
  );
}
