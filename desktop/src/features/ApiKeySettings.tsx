import { useEffect, useState } from "react";

import { ConfirmDialog } from "../components/ConfirmDialog";
import {
  API_KEY_SERVICES,
  deleteApiCredential,
  listApiCredentials,
  saveApiCredential,
  testApiCredential,
  type ApiCredentialConnection,
  type ApiCredentialStatus,
  type ApiServiceId,
} from "../credential-api";
import "./ApiKeySettings.css";

const SOURCE_LABEL: Record<ApiCredentialStatus["source"], string> = {
  saved: "OS 보안 저장소에 저장됨",
  environment: "환경변수에서 제공됨",
  disabled: "사용 해제됨",
  none: "등록 안 됨",
};

export function CredentialEditor({
  credential, value, busy, connected, onChange, onSave, onDelete, onTest,
}: {
  credential: ApiCredentialStatus;
  value: string;
  busy: boolean;
  connected: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
  onDelete: () => void;
  onTest: () => void;
}) {
  const label = API_KEY_SERVICES.find((service) => service.id === credential.service_id)?.label;
  const inputId = `api-key-${credential.service_id}`;
  return (
    <form className="api-key-editor" onSubmit={(event) => { event.preventDefault(); onSave(); }}>
      <label htmlFor={inputId}>{label}</label>
      <p className="muted" role="status">{SOURCE_LABEL[credential.source]}</p>
      {!credential.supported && <p className="muted">이 운영체제에서는 보안 키 저장을 지원하지 않습니다.</p>}
      <input id={inputId} type="password" name={inputId} value={value}
        autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false}
        maxLength={8192} placeholder="새 API 키 입력 · 저장된 키는 표시하지 않습니다"
        aria-label={`${label} API 키`} disabled={busy || !credential.supported}
        onChange={(event) => onChange(event.target.value)} />
      <div className="button-row">
        <button className="quiet-button" type="submit"
          disabled={busy || !credential.supported || !value.trim()}>
          키 저장 · 적용
        </button>
        <button className="quiet-button" type="button" onClick={onDelete}
          disabled={busy || !credential.supported || !credential.configured}>
          키 사용 해제…
        </button>
        <button className="quiet-button" type="button" onClick={onTest}
          disabled={busy || !connected || !credential.configured}>
          실제 연결 확인
        </button>
      </div>
    </form>
  );
}

export function ApiKeySettings({
  connected, onRefresh,
}: { connected: boolean; onRefresh?: () => void | Promise<void> }) {
  const [credentials, setCredentials] = useState<ApiCredentialStatus[]>([]);
  const [drafts, setDrafts] = useState<Partial<Record<ApiServiceId, string>>>({});
  const [checks, setChecks] = useState<Partial<Record<ApiServiceId, ApiCredentialConnection>>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<ApiServiceId | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiServiceId | null>(null);

  useEffect(() => {
    let cancelled = false;
    listApiCredentials().then((result) => {
      if (!cancelled) setCredentials(result);
    }).catch((cause: unknown) => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function refreshStatus() {
    setLoading(true);
    setError(null);
    try {
      setCredentials(await listApiCredentials());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }

  async function changeCredential(service: ApiServiceId, remove: boolean) {
    if (busy) return;
    const value = drafts[service]?.trim() ?? "";
    if (!remove && !value) return;
    setBusy(service);
    setError(null);
    setNotice(null);
    try {
      if (remove) await deleteApiCredential(service);
      else await saveApiCredential(service, value);
      setDrafts((current) => ({ ...current, [service]: "" }));
      setChecks((current) => {
        const next = { ...current };
        delete next[service];
        return next;
      });
      setDeleteTarget(null);
      setNotice(remove
        ? "API 키 사용을 해제하고 적용했습니다. 환경변수의 키도 이 앱에서는 사용하지 않습니다."
        : "API 키를 OS 보안 저장소에 저장하고 적용했습니다. 입력란을 비웠습니다.");
      await refreshStatus();
      await onRefresh?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setDeleteTarget(null);
    } finally {
      setBusy(null);
    }
  }

  async function checkConnection(service: ApiServiceId) {
    if (busy || !connected) return;
    setBusy(service);
    setError(null);
    try {
      const result = await testApiCredential(service);
      setChecks((current) => ({ ...current, [service]: result }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="api-key-settings workspace" aria-labelledby="api-key-settings-title">
      <h2 id="api-key-settings-title">개인 API 키</h2>
      <p className="muted">키는 macOS 키체인 또는 Windows 자격 증명 관리자에 보관합니다.
        가족 기록·백업 파일에는 넣지 않으며 저장된 키를 화면으로 다시 가져오지 않습니다.</p>
      <p className="muted">저장·해제하면 로컬 서비스를 다시 연결해 바로 적용합니다.
        원격 AI 키를 저장해도 아동 기록의 원격 전송 동의 설정은 자동으로 바뀌지 않습니다.</p>
      {loading && <p role="status">API 키 등록 상태를 확인하고 있습니다.</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!loading && <button className="quiet-button" type="button" disabled={busy !== null}
        onClick={() => void refreshStatus()}>등록 상태 다시 확인</button>}
      <div className="api-key-list">
        {credentials.map((credential) => (
          <div key={credential.service_id}>
            <CredentialEditor credential={credential} value={drafts[credential.service_id] ?? ""}
              busy={busy !== null || loading} connected={connected}
              onChange={(value) => setDrafts((current) => ({ ...current, [credential.service_id]: value }))}
              onSave={() => void changeCredential(credential.service_id, false)}
              onDelete={() => setDeleteTarget(credential.service_id)}
              onTest={() => void checkConnection(credential.service_id)} />
            {checks[credential.service_id] && <p className="muted"
              role={checks[credential.service_id]?.status === "unavailable" ? "alert" : "status"}>
              {checks[credential.service_id]?.message}
            </p>}
          </div>
        ))}
      </div>
      <ConfirmDialog open={deleteTarget !== null} title="이 API 키의 사용을 해제할까요?"
        description="이 앱에 저장된 키를 지우고 환경변수의 키도 사용하지 않습니다. 다시 쓰려면 새 키를 저장해 주세요."
        confirmLabel="키 사용 해제" destructive busy={busy !== null}
        onConfirm={() => { if (deleteTarget) void changeCredential(deleteTarget, true); }}
        onCancel={() => setDeleteTarget(null)} />
    </section>
  );
}
