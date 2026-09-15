import type { ReactNode } from "react";

// Safe Markdown renderer for parent-facing material drafts.
//
// Materials are untrusted drafts (template- or AI-generated), so this component
// NEVER injects raw HTML. It parses the small Markdown subset the generators
// actually emit -- headings, ordered/unordered lists, GFM tables, blockquotes,
// fenced/inline code, and bold/italic emphasis -- into plain React elements.
// Because every leaf is a React text node, any embedded HTML (e.g. a stray
// `<script>` or `<img onerror=...>`) is escaped by React and stays inert. There
// is no `dangerouslySetInnerHTML` anywhere in this path.

interface MaterialContentProps {
  markdown: string;
  className?: string;
}

const INLINE_CODE = /`([^`]+)`/;
const BOLD = /\*\*([^*]+)\*\*|__([^_]+)__/;
const ITALIC = /\*([^*]+)\*|_([^_]+)_/;
const TABLE_DELIMITER = /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$/;

type Align = "left" | "center" | "right" | undefined;

// --- inline parsing ----------------------------------------------------------

// Renders inline emphasis/code by repeatedly locating the earliest token in the
// remaining text. Precedence: inline code > bold > italic. This is ITERATIVE over
// the trailing text (not recursive) so a pathological paragraph with tens of
// thousands of inline tokens can never overflow the call stack. Only the bounded,
// shallow emphasis *nesting* recurses. Everything resolves to strings inside React
// elements, so nothing is ever interpreted as markup.
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let remaining = text;
  let i = 0;
  while (remaining) {
    const code = INLINE_CODE.exec(remaining);
    const bold = BOLD.exec(remaining);
    const italic = ITALIC.exec(remaining);

    const candidates = [
      code ? { kind: "code" as const, index: code.index, match: code } : null,
      bold ? { kind: "bold" as const, index: bold.index, match: bold } : null,
      italic ? { kind: "italic" as const, index: italic.index, match: italic } : null,
    ].filter((entry): entry is NonNullable<typeof entry> => entry !== null);

    if (candidates.length === 0) {
      nodes.push(remaining);
      break;
    }

    candidates.sort((a, b) => a.index - b.index);
    const chosen = candidates[0];
    const { match } = chosen;
    // `before` cannot contain an earlier token (chosen is the earliest), so it is plain text.
    const before = remaining.slice(0, match.index);
    const inner = match[1] ?? match[2] ?? "";
    if (before) nodes.push(before);

    if (chosen.kind === "code") {
      nodes.push(<code key={`${keyPrefix}-${i}c`}>{inner}</code>);
    } else if (chosen.kind === "bold") {
      nodes.push(<strong key={`${keyPrefix}-${i}s`}>{renderInline(inner, `${keyPrefix}-${i}si`)}</strong>);
    } else {
      nodes.push(<em key={`${keyPrefix}-${i}e`}>{renderInline(inner, `${keyPrefix}-${i}ei`)}</em>);
    }

    remaining = remaining.slice(match.index + match[0].length);
    i += 1;
  }
  return nodes;
}

// --- table parsing -----------------------------------------------------------

function splitRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function parseAlignments(delimiter: string): Align[] {
  return splitRow(delimiter).map((cell) => {
    const left = cell.startsWith(":");
    const right = cell.endsWith(":");
    if (left && right) return "center";
    if (right) return "right";
    if (left) return "left";
    return undefined;
  });
}

function renderTable(headerLine: string, delimiterLine: string, bodyLines: string[], key: string): ReactNode {
  const headers = splitRow(headerLine);
  const aligns = parseAlignments(delimiterLine);
  const rows = bodyLines.map((line) => splitRow(line));

  return (
    <table key={key} className="material-content-table">
      <thead>
        <tr>
          {headers.map((cell, i) => (
            <th key={i} scope="col" style={aligns[i] ? { textAlign: aligns[i] } : undefined}>
              {renderInline(cell, `${key}h${i}`)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((cells, r) => (
          <tr key={r}>
            {cells.map((cell, c) => (
              <td key={c} style={aligns[c] ? { textAlign: aligns[c] } : undefined}>
                {renderInline(cell, `${key}r${r}c${c}`)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// --- block parsing -----------------------------------------------------------

function isTableStart(lines: string[], i: number): boolean {
  return (
    lines[i].includes("|") &&
    i + 1 < lines.length &&
    TABLE_DELIMITER.test(lines[i + 1]) &&
    lines[i + 1].includes("-")
  );
}

function renderBlocks(markdown: string): ReactNode[] {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    const k = `b${key++}`;

    // Blank line -> block separator.
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Fenced code block.
    const fence = /^\s*```/.exec(line);
    if (fence) {
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !/^\s*```/.test(lines[i])) {
        codeLines.push(lines[i]);
        i += 1;
      }
      i += 1; // consume closing fence (if present)
      blocks.push(
        <pre key={k} className="material-content-code">
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Heading.
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2].trim();
      const Tag = `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
      blocks.push(<Tag key={k}>{renderInline(text, k)}</Tag>);
      i += 1;
      continue;
    }

    // Table.
    if (isTableStart(lines, i)) {
      const headerLine = lines[i];
      const delimiterLine = lines[i + 1];
      const bodyLines: string[] = [];
      let j = i + 2;
      while (j < lines.length && lines[j].includes("|") && lines[j].trim() !== "") {
        bodyLines.push(lines[j]);
        j += 1;
      }
      blocks.push(renderTable(headerLine, delimiterLine, bodyLines, k));
      i = j;
      continue;
    }

    // Blockquote (a figure/callout in the drafts).
    if (/^\s*>\s?/.test(line)) {
      const quoteLines: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quoteLines.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      blocks.push(
        <blockquote key={k}>
          {quoteLines.map((q, qi) => (
            <p key={qi}>{renderInline(q, `${k}q${qi}`)}</p>
          ))}
        </blockquote>,
      );
      continue;
    }

    // Unordered list.
    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ul key={k}>
          {items.map((item, ii) => (
            <li key={ii}>{renderInline(item, `${k}i${ii}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    // Ordered list.
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ol key={k}>
          {items.map((item, ii) => (
            <li key={ii}>{renderInline(item, `${k}i${ii}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    // Paragraph: gather contiguous non-blank, non-block lines.
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^\s*```/.test(lines[i]) &&
      !/^(#{1,6})\s+/.test(lines[i]) &&
      !/^\s*>\s?/.test(lines[i]) &&
      !/^\s*[-*+]\s+/.test(lines[i]) &&
      !/^\s*\d+[.)]\s+/.test(lines[i]) &&
      !isTableStart(lines, i)
    ) {
      paraLines.push(lines[i]);
      i += 1;
    }
    if (paraLines.length > 0) {
      const text = paraLines.join(" ");
      blocks.push(<p key={k}>{renderInline(text, k)}</p>);
    } else {
      i += 1; // safety: never spin on a line we could not classify
    }
  }

  return blocks;
}

export function MaterialContent({ markdown, className }: MaterialContentProps) {
  const rootClass = className ? `material-content ${className}` : "material-content";
  const source = markdown ?? "";

  if (source.trim() === "") {
    return <div className={rootClass} data-empty="true" />;
  }

  return <div className={rootClass}>{renderBlocks(source)}</div>;
}
