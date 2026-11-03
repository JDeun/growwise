import { useEffect, useState } from "react";

import { chooseStorageLocation, getStorageLocation, relocateStorage } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";

const RELOCATION_WARNING_KEY = "growwise:relocation-warning";

export function StorageSettings({ connected }: { connected: boolean }) {
  const [location, setLocation] = useState<string | null>(null);
  const [destination, setDestination] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(() => {
    try { return window.localStorage.getItem(RELOCATION_WARNING_KEY); }
    catch { return null; }
  });

  useEffect(() => {
    try { window.localStorage.removeItem(RELOCATION_WARNING_KEY); }
    catch { /* A blocked browser store must not hide the warning already on screen. */ }
  }, []);

  useEffect(() => {
    if (!connected) return;
    let current = true;
    void getStorageLocation().then(
      (path) => { if (current) setLocation(path); },
      (reason: unknown) => { if (current) setError(String(reason)); },
    );
    return () => { current = false; };
  }, [connected]);

  async function choose() {
    setError(null);
    try { setDestination(await chooseStorageLocation()); }
    catch (reason) { setError(String(reason)); }
  }

  async function relocate() {
    if (!destination || busy) return;
    setBusy(true);
    setError(null);
    try {
      const committedWarning = await relocateStorage(destination);
      if (committedWarning) {
        try { window.localStorage.setItem(RELOCATION_WARNING_KEY, committedWarning); }
        catch { window.alert(committedWarning); }
      }
      // Discard every cached child/entity after reconnecting to the verified data copy.
      window.location.reload();
    } catch (reason) {
      setError(String(reason));
      setBusy(false);
      setDestination(null);
    }
  }

  return (
    <article className="status-card">
      <h2>기록 저장 위치</h2>
      <p className="muted" style={{ overflowWrap: "anywhere" }}>{location ?? "연결 후 확인할 수 있습니다."}</p>
      <p className="muted">아이 기록·사진·대화·백업을 함께 이전합니다. 이전 위치의 사본은 복구용으로 남습니다.</p>
      <button className="quiet-button" type="button" disabled={!connected || busy} onClick={() => void choose()}>
        저장 폴더 변경
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
      {warning && (
        <div role="alert">
          <p>{warning}</p>
          <button type="button" className="quiet-button" onClick={() => setWarning(null)}>확인</button>
        </div>
      )}
      <ConfirmDialog
        open={destination !== null}
        title="저장 폴더를 변경할까요?"
        description={`새 위치: ${destination ?? ""}. 저장 중인 작업이 잠시 중단되며, 복사 검증 후 화면을 다시 엽니다. 기존 사본에도 개인정보가 남으므로 필요 없을 때 직접 정리해 주세요.`}
        confirmLabel={busy ? "이전 중…" : "이 위치로 이전"}
        busy={busy}
        onConfirm={() => void relocate()}
        onCancel={() => setDestination(null)}
      />
    </article>
  );
}
