import type { ResourceDetailsDraft } from "../resource-details";

export function ResourceDetailsFields({ value, onChange, disabled = false }: {
  value: ResourceDetailsDraft;
  onChange: (value: ResourceDetailsDraft) => void;
  disabled?: boolean;
}) {
  const set = (field: keyof ResourceDetailsDraft, next: string) => onChange({ ...value, [field]: next });
  return (
    <details className="resource-details-fields">
      <summary>출처·분류 설정(선택)</summary>
      <div className="resource-details-grid">
        <label><span>요약</span><textarea maxLength={20000} value={value.summary} disabled={disabled}
          onChange={(event) => set("summary", event.target.value)} /></label>
        <label><span>출처 이름</span><input maxLength={500} value={value.sourceName} disabled={disabled}
          placeholder="예: 시립도서관, 직접 작성" onChange={(event) => set("sourceName", event.target.value)} /></label>
        <label><span>출처 URL</span><input type="url" maxLength={2048} value={value.sourceUrl} disabled={disabled}
          placeholder="https://…" onChange={(event) => set("sourceUrl", event.target.value)} /></label>
        <label><span>저자·작성자</span><input maxLength={500} value={value.author} disabled={disabled}
          onChange={(event) => set("author", event.target.value)} /></label>
        <label><span>태그</span><input value={value.tags} disabled={disabled}
          placeholder="예: 자연, 그림책, 관찰" onChange={(event) => set("tags", event.target.value)} />
          <small>쉼표로 구분합니다. 태그는 100개까지, 각 200자까지 저장합니다.</small></label>
      </div>
    </details>
  );
}

export function ResourceScopeField({ value, onChange, disabled = false }: {
  value: ResourceDetailsDraft["scope"];
  onChange: (value: ResourceDetailsDraft["scope"]) => void;
  disabled?: boolean;
}) {
  return (
    <div className="resource-scope-field">
      <label><span>사용 범위</span><select value={value} disabled={disabled}
        onChange={(event) => onChange(event.target.value as ResourceDetailsDraft["scope"])}>
        <option value="child">현재 아이에 저장</option>
        <option value="shared">이 기기의 모든 아이와 공유</option>
      </select></label>
      <p className="muted">{value === "shared"
        ? "모든 아이 화면의 검색과 자료 생성에서 사용할 수 있습니다. 개인 관찰·민감한 정보는 넣지 마세요. 인터넷에 공개되지는 않습니다."
        : "현재 아이의 자료로 저장합니다. 따로 연결한 아이는 ‘다른 아이와 자료 연결’에서 관리합니다. 공용 자료를 현재 아이로 바꾸면 기존 아이 연결을 해제합니다."}</p>
    </div>
  );
}
