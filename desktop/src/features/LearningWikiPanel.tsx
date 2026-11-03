import { useEffect, useState } from "react";

import { MaterialContent } from "../components/MaterialContent";
import { getLearningWiki, rebuildLearningWiki, type LearningWiki } from "../learning-wiki-api";

export function LearningWikiContent({ wiki }: { wiki: LearningWiki }) {
  const sourceRefs = new Set(wiki.source_refs);
  const markdown = wiki.content_markdown.split("\n").filter((line) => {
    if (!line.startsWith("  - 근거: ")) return true;
    const refs = line.slice("  - 근거: ".length).split(", ");
    // Only hide the renderer's exact, known-reference evidence lines; provenance stays below.
    return !refs.every((ref) => ref.startsWith("`") && ref.endsWith("`")
      && sourceRefs.has(ref.slice(1, -1)));
  }).join("\n");
  return (
    <>
      <p className="muted">
        원본 기록에서 다시 정리한 맥락입니다. 아이의 능력이나 발달에 대한 판정이 아닙니다.
      </p>
      <p className="muted">
        {wiki.generator_mode === "llm_wiki"
          ? "AI가 정리를 보조했습니다. 해석은 연결된 원본 기록과 함께 확인해 주세요."
          : "AI 없이 원본 기록의 질문과 다음 활동을 모아 정리했습니다."}
      </p>
      {wiki.source_refs.length === 0 ? (
        <p>의미 있는 질문이나 경험을 남기면 관심과 다음 활동의 연결을 이곳에서 확인할 수 있습니다.</p>
      ) : (
        <MaterialContent markdown={markdown} />
      )}
      <details>
        <summary>정리 근거 · 기록 {wiki.source_refs.length}개 · 버전 {wiki.revision}</summary>
        <p>원본 기록이 바뀌면 이 맥락도 다시 만들 수 있습니다. 원본은 그대로 보존됩니다.</p>
        <ul aria-label="성장 맥락의 원본 기록">
          {wiki.source_refs.map((ref) => <li key={ref}><code>{ref}</code></li>)}
        </ul>
      </details>
    </>
  );
}

export function LearningWikiPanel({ childId }: { childId: string }) {
  const [refresh, setRefresh] = useState(0);
  const [wiki, setWiki] = useState<LearningWiki | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    const request = refresh ? rebuildLearningWiki(childId) : getLearningWiki(childId);
    void request.then((result) => {
      if (!cancelled && result.child_id === childId) setWiki(result);
    }).catch((cause: unknown) => {
      if (!cancelled) {
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    }).finally(() => {
      if (!cancelled) setBusy(false);
    });
    return () => { cancelled = true; };
  }, [childId, refresh]);

  return (
    <section className="profile-tab-context learning-wiki-panel" aria-label="기록에서 이어지는 성장 맥락">
      <h3>기록에서 이어지는 성장 맥락</h3>
      {busy && <p role="status">원본 기록에서 관심과 이어지는 질문을 정리하고 있습니다.</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {wiki?.child_id === childId && <LearningWikiContent wiki={wiki} />}
      <button className="quiet-button" type="button" disabled={busy} onClick={() => setRefresh((n) => n + 1)}>
        {busy ? "정리 중…" : "원본 기록에서 다시 정리"}
      </button>
    </section>
  );
}
