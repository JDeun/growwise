import { invoke, isTauri } from "@tauri-apps/api/core";
import { useState, type MouseEvent, type ReactNode } from "react";

import "./ExternalSourceLink.css";

export function externalHttpUrl(value: string): string | null {
  if (!value || value.length > 8192 || value.trim() !== value || [...value].some((character) => {
    const code = character.charCodeAt(0);
    return code <= 32 || (code >= 127 && code <= 159);
  })) return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export async function openNativeSource(url: string): Promise<void> {
  const safe = externalHttpUrl(url);
  if (!safe) throw new Error("올바른 HTTP(S) 출처 주소가 아닙니다.");
  await invoke("open_external_url", { url: safe });
}

export function ExternalSourceLink({ href, children }: { href: string; children: ReactNode }) {
  const [error, setError] = useState(false);
  const [opening, setOpening] = useState(false);
  const url = externalHttpUrl(href);
  if (!url) return null;

  async function open(event: MouseEvent<HTMLAnchorElement>) {
    // Browser previews retain normal link navigation; desktop opens the OS default browser.
    if (!isTauri()) return;
    event.preventDefault();
    if (opening) return;
    setOpening(true);
    setError(false);
    try { await openNativeSource(href); }
    catch { setError(true); }
    finally { setOpening(false); }
  }

  return (
    <span className="external-source-link">
      <a href={url} target="_blank" rel="noopener noreferrer" aria-busy={opening || undefined}
        onClick={(event) => void open(event)}
        onAuxClick={(event) => { if (event.button === 1) void open(event); }}>{children}</a>
      {error && <small role="alert">브라우저를 열지 못했습니다. 기본 브라우저 설정을 확인한 뒤 다시 눌러 주세요.</small>}
    </span>
  );
}
