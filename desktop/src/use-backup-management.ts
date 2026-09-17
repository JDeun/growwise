import { useCallback, useState } from "react";

import {
  createBackup,
  exportBackup,
  importBackup,
  listBackups,
  restoreBackup,
  type BackupItem,
} from "./api";
import { errorMessage } from "./child-context-state";

export type BackupConfirmation =
  | { kind: "import" }
  | { kind: "restore"; archiveName: string };

export function useBackupManagement() {
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [backupBusy, setBackupBusy] = useState(false);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [backupNotice, setBackupNotice] = useState<string | null>(null);
  const [backupConfirmation, setBackupConfirmation] = useState<BackupConfirmation | null>(null);

  const refreshBackups = useCallback(async () => {
    try {
      setBackups(await listBackups());
      setBackupError(null);
    } catch (error) {
      setBackups([]);
      setBackupError(errorMessage(error, "백업 목록을 불러오지 못했습니다."));
    }
  }, []);

  async function handleCreateBackup() {
    setBackupBusy(true);
    setBackupError(null);
    setBackupNotice(null);
    try {
      await createBackup();
      await refreshBackups();
      setBackupNotice("새 백업을 만들었습니다.");
    } catch (error) {
      setBackupError(errorMessage(error, "백업 생성에 실패했습니다."));
    } finally {
      setBackupBusy(false);
    }
  }

  async function handleExportBackup(archiveName: string) {
    setBackupBusy(true);
    setBackupError(null);
    setBackupNotice(null);
    try {
      await exportBackup(archiveName);
      setBackupNotice("백업 ZIP 내보내기를 완료했습니다.");
    } catch (error) {
      setBackupError(errorMessage(error, "백업 내보내기에 실패했습니다."));
    } finally {
      setBackupBusy(false);
    }
  }

  function handleImportBackup() {
    if (backupBusy) return;
    setBackupError(null);
    setBackupNotice(null);
    setBackupConfirmation({ kind: "import" });
  }

  function handleRestoreBackup(archiveName: string) {
    if (backupBusy) return;
    setBackupError(null);
    setBackupNotice(null);
    setBackupConfirmation({ kind: "restore", archiveName });
  }

  async function confirmBackupAction(): Promise<boolean> {
    const action = backupConfirmation;
    if (!action) return false;
    setBackupBusy(true);
    setBackupError(null);
    setBackupNotice(null);
    try {
      if (action.kind === "import") {
        const result = await importBackup();
        setBackupConfirmation(null);
        if (!result) return false;
        setBackupNotice("외부 백업을 가져왔습니다.");
        return true;
      }
      await restoreBackup(action.archiveName);
      setBackupConfirmation(null);
      setBackupNotice("백업을 복원했습니다.");
      return true;
    } catch (error) {
      setBackupError(
        errorMessage(
          error,
          action.kind === "import"
            ? "외부 백업 가져오기에 실패했습니다."
            : "백업 복원에 실패했습니다.",
        ),
      );
      return false;
    } finally {
      setBackupBusy(false);
    }
  }

  function handleCancelBackupAction() {
    if (!backupBusy) setBackupConfirmation(null);
  }

  const backupConfirmationTitle =
    backupConfirmation?.kind === "restore" ? "백업으로 복원하기" : "외부 백업 가져오기";
  const backupConfirmationDescription =
    backupConfirmation?.kind === "restore"
      ? `현재 기록을 ${backupConfirmation.archiveName} 백업으로 교체합니다. 복원 전에 현재 상태를 별도 백업하는 것을 권장합니다.`
      : "외부 GrowWise ZIP을 가져오면 현재 기록을 교체합니다. 가져오기 직전에 현재 상태를 자동 보호 백업합니다.";
  const backupConfirmationLabel =
    backupConfirmation?.kind === "restore" ? "이 백업 복원" : "가져오기 계속";

  return {
    backups,
    backupBusy,
    backupError,
    backupNotice,
    backupConfirmation,
    backupConfirmationTitle,
    backupConfirmationDescription,
    backupConfirmationLabel,
    refreshBackups,
    handleCreateBackup,
    handleExportBackup,
    handleImportBackup,
    handleRestoreBackup,
    confirmBackupAction,
    handleCancelBackupAction,
  };
}
