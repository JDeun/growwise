import { useEffect, useState } from "react";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { appUpdateStatus, checkAppUpdate, installAppUpdate, type AppUpdateStatus } from "../updater-api";
import "./UpdaterSettings.css";

export function UpdateSummary({ status }: { status: AppUpdateStatus }) {
  return (
    <>
      <p className="muted">현재 버전 {status.current_version}</p>
      {!status.configured ? <p>이 설치본은 자동 업데이트가 설정되지 않았습니다.</p>
        : status.available_version ? <p>새 버전 {status.available_version}을 설치할 수 있습니다.</p>
          : status.checked ? <p>현재 설치된 버전이 최신입니다.</p>
            : <p>업데이트를 확인하면 공개 배포 서버에 앱 버전과 운영체제 정보를 보냅니다. 아이 기록은 보내지 않습니다.</p>}
      {status.available_version && status.notes && <details>
        <summary>업데이트 내용</summary><pre className="update-release-notes">{status.notes}</pre>
      </details>}
    </>
  );
}

export function UpdaterSettings() {
  const [status, setStatus] = useState<AppUpdateStatus | null>(null);
  const [busy, setBusy] = useState<"check" | "install" | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    appUpdateStatus().then((value) => { if (active) setStatus(value); })
      .catch(() => { if (active) setError("업데이트 상태를 불러오지 못했습니다."); });
    return () => { active = false; };
  }, []);

  async function check() {
    if (busy) return;
    setBusy("check"); setError(null);
    try { setStatus(await checkAppUpdate()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(null); }
  }

  async function install() {
    const version = status?.available_version;
    if (busy || !version) return;
    setBusy("install"); setError(null);
    try { await installAppUpdate(version); }
    catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setStatus((current) => current ? { ...current, available_version: null, checked: false } : current);
      setConfirm(false); setBusy(null);
    }
  }

  return (
    <section className="updater-settings data-section-divider" aria-labelledby="app-update-title">
      <h2 id="app-update-title">앱 업데이트</h2>
      {status && <UpdateSummary status={status} />}
      {!status && !error && <p role="status">업데이트 상태를 확인하는 중…</p>}
      {status?.configured && <div className="button-row">
        <button type="button" className="quiet-button" disabled={busy !== null} onClick={() => void check()}>
          {busy === "check" ? "확인 중…" : "새 버전 확인"}
        </button>
        {status.available_version && <button type="button" className="quiet-button"
          disabled={busy !== null} onClick={() => setConfirm(true)}>다운로드·설치…</button>}
      </div>}
      {busy === "install" && <p role="status">업데이트를 내려받고 서명을 확인하는 중입니다. 설치가 끝나면 앱을 다시 시작합니다.</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <ConfirmDialog open={confirm} title={busy === "install" ? "앱을 업데이트하는 중입니다" : "새 버전을 설치할까요?"}
        description={busy === "install"
          ? "업데이트를 내려받고 서명을 확인하는 중입니다. 설치가 끝나면 앱을 다시 시작합니다. 다운로드나 서명 확인이 실패하면 설치하지 않고 이 창을 닫습니다."
          : "작성 중인 내용을 먼저 저장해 주세요. 파일의 서명을 확인한 뒤 Core를 멈추고 앱을 업데이트·재시작합니다. 다운로드나 서명 확인이 실패하면 설치하지 않습니다."}
        confirmLabel="다운로드·설치·재시작" busy={busy === "install"}
        onConfirm={() => void install()} onCancel={() => setConfirm(false)} />
    </section>
  );
}
