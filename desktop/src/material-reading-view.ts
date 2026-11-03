const PUBLICATION_MARKER = "> GrowWise 활동 자료 · 부모가 내용을 확인한 뒤 사용합니다.";
const CURRICULUM_METADATA = /^- (교육과정 연결|적용 교육과정|기준 고시):/;

/** Present standard publications for reading without altering their authoritative Markdown. */
export function materialReadingMarkdown(markdown: string): string {
  const lines = markdown.split(/\r?\n/);
  const marker = lines.indexOf(PUBLICATION_MARKER);
  if (marker < 0) return markdown;
  const title = lines.findIndex((line) => line.trim() !== "");
  if (title < 0 || !lines[title].startsWith("# ")
      || lines.findIndex((line, index) => index > title && line.trim() !== "") !== marker) return markdown;
  const core = lines.findIndex((line, index) => index > marker && line === "## 활동 자료");
  if (core < 0) return markdown;

  const visible: string[] = [];
  let inCriteria = false;
  let section = "";
  for (const [index, line] of lines.entries()) {
    // Only the known publication preamble is projected. Learner-authored core sections,
    // hints and reflection retain their complete text, even if they reuse these labels.
    if (index > marker && index < core) {
      if (/^## /.test(line)) section = line;
      if (line === "## 단계별 활동 기준") {
        inCriteria = true;
        continue;
      }
      if (/^#{1,2} /.test(line)) inCriteria = false;
      if (inCriteria || (section === "## 오늘의 목표" && CURRICULUM_METADATA.test(line))) continue;
    }
    visible.push(line);
  }
  return visible.join("\n");
}
