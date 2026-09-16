import type { ViewLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { GrowthMap } from "../api";
import { axisLabel, diversityLabel } from "../presentation";
import "./GrowthContextPanel.css";

interface GrowthContextPanelProps {
  growthState: ViewLoadState;
  growthMap: GrowthMap | null;
  onRetry: () => void;
}

const LAYER_HELP: Record<GrowthMap["layers"][number]["key"], string> = {
  whole_person: "신체·정서·표현·사회성 등 생활 전반에서 어떤 경험이 기록됐는지 봅니다.",
  learning: "읽기·말하기·쓰기·수학·탐색처럼 학습 경험이 어디에 연결됐는지 봅니다.",
  stage_focus: "현재 교육 단계에서 특히 살펴볼 만한 경험을 별도 렌즈로 모아 봅니다.",
};

export function GrowthContextPanel({ growthState, growthMap, onRetry }: GrowthContextPanelProps) {
  if (growthState.kind === "loading") {
    return (
      <article className="observation-result growth-context-panel">
        <p className="card-label">GROWTH CONTEXT</p>
        <h3>성장 맥락</h3>
        <ViewStateNotice
          kind="loading"
          title="성장 맥락을 불러오는 중입니다."
          description="다른 작업공간은 기다리지 않고 사용할 수 있습니다."
        />
      </article>
    );
  }

  if (growthState.kind === "error") {
    return (
      <article className="observation-result growth-context-panel">
        <p className="card-label">GROWTH CONTEXT</p>
        <h3>성장 맥락</h3>
        <ViewStateNotice
          kind="error"
          title="성장 맥락을 불러오지 못했습니다."
          description={growthState.message}
          action={
            <button className="quiet-button" type="button" onClick={onRetry}>
              다시 시도
            </button>
          }
        />
      </article>
    );
  }

  if (!growthMap || growthMap.total_logs_in_period === 0) {
    return (
      <article className="observation-result growth-context-panel">
        <p className="card-label">GROWTH CONTEXT</p>
        <h3>최근 {growthMap?.period_days ?? 30}일</h3>
        <ViewStateNotice
          kind="empty"
          title="아직 최근 관찰 기록이 없습니다."
          description="관찰을 기록하면 경험 축과 성장 맥락이 이곳에 누적됩니다."
        />
      </article>
    );
  }

  const observedAxes = growthMap.axes.filter((axis) => axis.observation_count > 0);
  const sortedAxes = [...growthMap.axes].sort(
    (left, right) => right.observation_count - left.observation_count,
  );
  const maxCount = Math.max(1, ...sortedAxes.map((axis) => axis.observation_count));
  const taggedRatio = Math.round(
    (growthMap.tagged_logs_in_period / Math.max(1, growthMap.total_logs_in_period)) * 100,
  );

  return (
    <article className="observation-result growth-context-panel">
      <div className="growth-context-heading">
        <div>
          <p className="card-label">GROWTH CONTEXT</p>
          <h3>최근 {growthMap.period_days}일의 기록 분포</h3>
          <p className="muted">
            아이를 점수화하지 않고, 부모가 남긴 관찰이 어떤 경험에 연결됐는지 보여줍니다.
          </p>
        </div>
        <span className={`growth-diversity-badge diversity-${growthMap.diversity.state}`}>
          {diversityLabel(growthMap.diversity.state)}
        </span>
      </div>

      <div className="growth-summary" aria-label="성장 맥락 요약">
        <article>
          <span>관찰 기록</span>
          <strong>{growthMap.total_logs_in_period}</strong>
          <small>최근 {growthMap.period_days}일</small>
        </article>
        <article>
          <span>경험 축 연결</span>
          <strong>{taggedRatio}%</strong>
          <small>{growthMap.tagged_logs_in_period}건에 축이 연결됨</small>
        </article>
        <article>
          <span>관찰된 경험 축</span>
          <strong>{observedAxes.length}</strong>
          <small>전체 {growthMap.axes.length}개 축 중</small>
        </article>
      </div>

      <section className="growth-coverage" aria-labelledby="growth-coverage-title">
        <div className="growth-section-heading">
          <div>
            <h4 id="growth-coverage-title">경험 축 커버리지</h4>
            <p>막대 길이는 최근 기록 횟수의 상대적 크기이며 능력·성취 수준을 뜻하지 않습니다.</p>
          </div>
        </div>
        <div className="growth-axis-list">
          {sortedAxes.map((axis) => {
            const width =
              axis.observation_count === 0
                ? 0
                : Math.max(2, Math.round((axis.observation_count / maxCount) * 100));
            return (
              <div className="growth-axis-row" key={axis.axis}>
                <div className="growth-axis-label">
                  <strong>{axisLabel(axis.axis)}</strong>
                  <span>{axis.observation_count}건</span>
                </div>
                <div
                  className="growth-axis-track"
                  role="img"
                  aria-label={`${axisLabel(axis.axis)} 관찰 ${axis.observation_count}건`}
                >
                  <span style={{ width: `${width}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="growth-lens-section" aria-labelledby="growth-lens-title">
        <div className="growth-section-heading">
          <div>
            <h4 id="growth-lens-title">세 가지 관찰 렌즈</h4>
            <p>같은 기록을 목적이 다른 렌즈로 다시 묶어, 한 영역만 과도하게 해석하지 않도록 합니다.</p>
          </div>
        </div>
        <div className="growth-layers growth-layers-explained">
          {growthMap.layers.map((layer) => {
            const populated = layer.axes.filter((axis) => axis.observation_count > 0);
            return (
              <section className="growth-layer" key={layer.key}>
                <div className="growth-layer-heading">
                  <strong>{layer.label}</strong>
                  <small>{LAYER_HELP[layer.key]}</small>
                </div>
                <div className="axis-summary">
                  {populated.map((axis) => (
                    <span key={axis.axis}>
                      {axisLabel(axis.axis)} · {axis.observation_count}
                    </span>
                  ))}
                </div>
                {populated.length === 0 && (
                  <small className="growth-layer-empty">
                    이 렌즈에 연결된 최근 기록이 아직 없습니다. 기록 없음은 부족함을 의미하지 않습니다.
                  </small>
                )}
              </section>
            );
          })}
        </div>
      </section>

      <div className={`diversity-note diversity-${growthMap.diversity.state}`}>
        <strong>{diversityLabel(growthMap.diversity.state)}</strong>
        <p>{growthMap.diversity.note}</p>
        {growthMap.diversity.focus_axes.length > 0 && (
          <small>
            최근 자주 기록된 경험: {growthMap.diversity.focus_axes.map(axisLabel).join(", ")}
          </small>
        )}
      </div>

      <details className="growth-explainability">
        <summary>이 화면은 어떻게 해석하나요?</summary>
        <div>
          <p>
            이 화면은 최근 관찰 기록의 <strong>분포</strong>를 설명합니다. 관찰 횟수는 아이의 능력,
            발달 단계, 성취도 점수가 아닙니다.
          </p>
          <ul>
            <li>기록이 많은 축은 최근 부모가 더 자주 관찰해 남긴 경험입니다.</li>
            <li>기록이 없는 축은 결핍이나 지연을 의미하지 않습니다.</li>
            <li>집중 상태는 기록이 일부 경험에 몰렸다는 뜻이며 진단 결과가 아닙니다.</li>
            <li>이 맥락은 다음 관찰이나 활동을 고를 때 참고하는 회고 도구로 사용합니다.</li>
          </ul>
        </div>
      </details>
    </article>
  );
}
