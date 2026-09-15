import "./OperationNotice.css";

interface OperationNoticeProps {
  message: string | null;
  onDismiss: () => void;
}

export function OperationNotice({ message, onDismiss }: OperationNoticeProps) {
  if (!message) return null;

  return (
    <aside className="operation-notice" role="status" aria-live="polite" aria-atomic="true">
      <span className="operation-notice-mark" aria-hidden="true">✓</span>
      <span>{message}</span>
      <button type="button" className="operation-notice-dismiss" onClick={onDismiss} aria-label="알림 닫기">
        ×
      </button>
    </aside>
  );
}
