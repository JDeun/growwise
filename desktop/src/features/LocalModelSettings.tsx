import { useCallback, useEffect, useState } from "react";

import { prepareLocalAi, type HealthResponse } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import {
  listLocalModels,
  removeLocalModel,
  setLocalModel,
  type InstalledLocalModel,
  type LocalModelComponent,
} from "../model-management-api";
import "./LocalModelSettings.css";

interface LocalModelSettingsProps {
  health: HealthResponse;
  onRefresh: () => void | Promise<void>;
}

const LABELS: Record<LocalModelComponent, string> = {
  text: "기록·자료 만들기",
  vision: "사진 이해",
  embedding: "검색 보강",
};

function sameModel(left: string, right: string | null | undefined): boolean {
  const tag = (value: string) => value.includes(":") ? value : `${value}:latest`;
  return Boolean(right && tag(left) === tag(right));
}

export function InstalledModelList({
  models,
  currentModel,
  busy,
  onSelect,
  onRemove,
}: {
  models: InstalledLocalModel[];
  currentModel: string | null | undefined;
  busy: boolean;
  onSelect: (name: string) => void;
  onRemove: (name: string) => void;
}) {
  if (models.length === 0) {
    return <p className="muted">이 로컬 AI에 설치된 모델이 없습니다. 필요한 모델을 준비해 주세요.</p>;
  }
  return (
    <ul className="local-model-list">
      {models.map((model) => (
        <li key={model.name}>
          <strong>{model.name}</strong>
          <span> · {(model.size / 1024 ** 3).toFixed(1)} GB</span>
          {sameModel(model.name, currentModel) && <span> · 현재 선택</span>}
          <div className="button-row">
            <button
              className="quiet-button"
              type="button"
              disabled={busy || sameModel(model.name, currentModel)}
              onClick={() => onSelect(model.name)}
              aria-label={`${model.name} 사용`}
            >
              이 모델 사용
            </button>
            <button
              className="quiet-button"
              type="button"
              disabled={busy}
              onClick={() => onRemove(model.name)}
              aria-label={`${model.name} 삭제`}
            >
              삭제…
            </button>
          </div>
          <details>
            <summary>설치 정보</summary>
            <p>Ollama 제공 digest: <code>{model.digest || "제공되지 않음"}</code></p>
            <p className="muted">이 값은 설치 메타데이터이며 현재 디스크 파일을 다시 검사한 결과는 아닙니다.</p>
          </details>
        </li>
      ))}
    </ul>
  );
}

export function LocalModelSettings({ health, onRefresh }: LocalModelSettingsProps) {
  const [component, setComponent] = useState<LocalModelComponent>("text");
  const [models, setModels] = useState<InstalledLocalModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removal, setRemoval] = useState<string | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const currentModel = component === "text" ? health.llm_model_id
    : component === "vision" ? health.vision_model_id : health.embedding_model_id;
  const endpoint = component === "text" ? health.llm_base_url
    : component === "vision" ? health.vision_base_url : health.embedding_base_url;

  const refreshModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await listLocalModels(component);
      setModels(next);
    } catch (cause) {
      setModels([]);
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, [component]);

  useEffect(() => {
    let current = true;
    setLoading(true);
    setModels([]);
    setError(null);
    setNotice(null);
    listLocalModels(component)
      .then((next) => { if (current) setModels(next); })
      .catch((cause: unknown) => {
        if (current) setError(cause instanceof Error ? cause.message : String(cause));
      })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [component, endpoint]);

  async function run(action: "select" | "remove" | "prepare", model?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (action === "select" && model) {
        await setLocalModel(component, model);
        setNotice("모델 선택을 저장하고 AI 연결을 다시 시작했습니다.");
      } else if (action === "remove" && model) {
        await removeLocalModel(component, model);
        setNotice("선택한 모델을 삭제했습니다. 아이 기록과 자료는 보존됩니다.");
      } else {
        await prepareLocalAi(component === "vision" ? "vision" : "basic");
        setNotice("필요한 모델 준비를 마쳤습니다.");
      }
      setRemoval(null);
      setSelection(null);
      await onRefresh();
      await refreshModels();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setRemoval(null);
      setSelection(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="status-card" aria-labelledby="local-model-heading">
      <h2 id="local-model-heading">로컬 AI 모델 관리</h2>
      <p className="muted">설치된 모델을 선택하거나 삭제합니다. 변경은 저장되며 다른 용도의 모델은 바뀌지 않습니다.</p>
      <label>
        모델 용도
        <select
          value={component}
          disabled={busy || loading}
          onChange={(event) => setComponent(event.target.value as LocalModelComponent)}
        >
          {Object.entries(LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <p>현재 선택: {currentModel ?? "미지정"}</p>
      <div className="button-row">
        <button className="quiet-button" type="button" disabled={busy || loading} onClick={() => void refreshModels()}>
          설치 목록 새로고침
        </button>
        <button className="quiet-button" type="button" disabled={busy || !endpoint} onClick={() => void run("prepare")}>
          필요한 모델 준비
        </button>
      </div>
      <p className="muted">모델 다운로드 시 Ollama가 무결성을 검증합니다. 설치 목록을 읽는 동작은 디스크 재검사가 아닙니다.</p>
      {loading && <p role="status">설치된 모델 확인 중…</p>}
      {busy && <p role="status">모델 변경 중입니다. 다운로드는 시간이 걸릴 수 있습니다.</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!loading && !error && <InstalledModelList
        models={models} currentModel={currentModel} busy={busy}
        onSelect={setSelection} onRemove={setRemoval}
      />}
      <ConfirmDialog
        open={removal !== null} title="로컬 모델을 삭제할까요?"
        description={`${removal ?? ""} 모델 파일을 Ollama에서 삭제합니다. 같은 Ollama를 사용하는 다른 앱에도 영향을 줄 수 있습니다. 이 모델을 사용하는 AI 기능은 다시 준비할 때까지 사용할 수 없습니다. 아이 기록·사진·자료는 삭제하지 않습니다.`}
        confirmLabel="모델 삭제" destructive busy={busy}
        onConfirm={() => { if (removal) void run("remove", removal); }}
        onCancel={() => setRemoval(null)}
      />
      <ConfirmDialog
        open={selection !== null} title="사용할 모델을 변경할까요?"
        description={`${LABELS[component]}에 ${selection ?? ""} 모델을 사용하도록 저장합니다. AI 연결을 다시 시작하므로 진행 중인 AI 작업은 재시도될 수 있습니다. 선택한 모델이 이 용도를 지원하는지 확인해 주세요.`}
        confirmLabel="이 모델 사용" busy={busy}
        onConfirm={() => { if (selection) void run("select", selection); }}
        onCancel={() => setSelection(null)}
      />
    </section>
  );
}
