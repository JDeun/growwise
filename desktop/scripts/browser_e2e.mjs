import { spawn } from "node:child_process";
import { createReadStream, existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { extname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = resolve(new URL("..", import.meta.url).pathname);
const DIST = join(ROOT, "dist");
const ARTIFACTS = join(ROOT, "artifacts", "browser-e2e");
const HOST = "127.0.0.1";
const PORT = 4173;
const DEBUG_PORT = 9222;
const BASE_URL = `http://${HOST}:${PORT}`;
const VIEWPORT = { width: 1672, height: 941 };

function invariant(condition, message) {
  if (!condition) throw new Error(message);
}

function contentType(file) {
  return {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
  }[extname(file)] ?? "application/octet-stream";
}

function startStaticServer() {
  invariant(existsSync(DIST), "desktop/dist is missing; run npm run build first");
  const server = createServer((req, res) => {
    const raw = new URL(req.url ?? "/", BASE_URL).pathname;
    const relative = raw === "/" ? "index.html" : raw.replace(/^\/+/, "");
    const candidate = resolve(DIST, relative);
    if (!candidate.startsWith(resolve(DIST))) {
      res.writeHead(403).end("forbidden");
      return;
    }
    const file = existsSync(candidate) ? candidate : join(DIST, "index.html");
    res.writeHead(200, { "Content-Type": contentType(file), "Cache-Control": "no-store" });
    createReadStream(file).pipe(res);
  });
  return new Promise((resolveServer, reject) => {
    server.once("error", reject);
    server.listen(PORT, HOST, () => resolveServer(server));
  });
}

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  const found = candidates.find((candidate) => existsSync(candidate));
  invariant(found, "headless Chrome/Chromium was not found on the CI runner");
  return found;
}

async function waitFor(fn, { timeoutMs = 15_000, intervalMs = 100, label = "condition" } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, intervalMs));
  }
  throw new Error(`timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ""}`);
}

class Cdp {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    this.socket = new WebSocket(this.url);
    await new Promise((resolveOpen, reject) => {
      this.socket.addEventListener("open", resolveOpen, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      if (payload.id) {
        const waiter = this.pending.get(payload.id);
        if (!waiter) return;
        this.pending.delete(payload.id);
        if (payload.error) waiter.reject(new Error(payload.error.message));
        else waiter.resolve(payload.result ?? {});
        return;
      }
      for (const listener of this.listeners.get(payload.method) ?? []) {
        listener(payload.params ?? {});
      }
    });
  }

  on(method, listener) {
    const current = this.listeners.get(method) ?? [];
    current.push(listener);
    this.listeners.set(method, current);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolveSend, reject) => {
      this.pending.set(id, { resolve: resolveSend, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    this.socket?.close();
  }
}

const child = {
  id: "018f7f00-1111-7111-8111-111111111111",
  nickname: "수아",
  stage: "elementary",
  age_months: 96,
  interests: ["자연", "독서", "그림"],
  primary_language: "ko",
  additional_languages: ["en"],
  learning_goals: ["관찰한 내용을 자기 말로 설명하기"],
  notes: "브라우저 E2E 합성 데이터",
  avatar_asset_id: "018f7f00-aaaa-7aaa-8aaa-aaaaaaaaaaaa",
};
const sibling = {
  ...child,
  id: "018f7f00-2222-7222-8222-222222222222",
  nickname: "하람",
  age_months: 60,
  stage: "preschool_3_5",
  avatar_asset_id: null,
};
const log = {
  id: "018f7f00-3333-7333-8333-333333333333",
  child_id: child.id,
  activity_plan_id: null,
  parent_observation: "공원에서 잎의 모양 차이를 비교하고 이유를 설명했습니다.",
  tags: ["자연", "관찰"],
  experience_axes: ["thinking_inquiry", "speaking"],
  interest: "식물",
  next_activity: "잎 모양 분류 카드 만들기",
  created_at: "2026-09-18T09:00:00+09:00",
  record_kind: "observation",
  title: "잎 모양 관찰",
  occurred_at: "2026-09-18T09:00:00+09:00",
  subject: "과학",
  institution: null,
  learner_work: "세 가지 잎을 모양별로 나눔",
  process: "관찰 → 비교 → 설명",
  child_question: "왜 잎 끝 모양이 달라?",
  difficulty_note: null,
  ai_status: "completed",
  ai_job_id: null,
  updated_at: "2026-09-18T09:10:00+09:00",
};
const resource = {
  id: "018f7f00-4444-7444-8444-444444444444",
  kind: "book",
  title: "우리 동네 나무 관찰",
  child_id: child.id,
  summary: "나뭇잎과 열매를 관찰하는 합성 참고 자료",
  content: "나무의 잎과 열매를 비교해 봅니다.",
  source_url: null,
  source_name: "GrowWise E2E fixture",
  author: "Synthetic",
  tags: ["자연", "과학"],
  stage_tags: ["elementary"],
  provenance: { source: "synthetic-e2e" },
  created_at: "2026-09-17T10:00:00+09:00",
  updated_at: "2026-09-17T10:00:00+09:00",
};
const material = {
  id: "018f7f00-5555-7555-8555-555555555555",
  child_id: child.id,
  kind: "science_inquiry",
  title: "잎 모양 비교 탐구",
  content_markdown: "# 잎 모양 비교 탐구\n\n## 오늘의 목표\n잎의 특징을 관찰하고 차이를 설명합니다.\n\n## 준비물\n잎 세 장, 돋보기, 연필\n\n## 활동 자료\n모양과 가장자리, 잎맥을 비교합니다.\n\n## 막힐 때 힌트\n색보다 모양부터 비교합니다.\n\n## 돌아보기\n가장 다른 잎은 무엇이었나요?\n\n## 더 해보기\n다른 장소의 잎도 비교합니다.",
  status: "review_pending",
  source_refs: [resource.id],
  source_citations: [],
  generator_mode: "template",
  review_note: null,
  request_topic: "나뭇잎",
  request_goal: "관찰한 차이를 설명한다.",
  version: 1,
  parent_material_id: null,
  version_note: null,
  curriculum_targets: [],
  parent_guide_markdown: "# 부모용 교안\n\n## 수업 개요\n아이의 관찰 표현을 기다립니다.\n\n## 질문·힌트 사다리\n무엇이 보이나요?\n\n## 난이도 조절\n비교 대상을 줄일 수 있습니다.\n\n## 안전·중단 기준\n야외 안전을 우선합니다.\n\n## 사용 전 확인\n부모가 확인한 뒤 사용합니다.",
  ai_status: "completed",
  ai_job_id: null,
  created_at: "2026-09-18T10:00:00+09:00",
  updated_at: "2026-09-18T10:00:00+09:00",
};
const activity = {
  id: "018f7f00-6666-7666-8666-666666666666",
  child_id: child.id,
  title: "동네 나무 세 종류 찾아보기",
  status: "active",
  source_refs: [resource.id],
  parent_note: null,
  started_at: "2026-09-18T08:00:00+09:00",
  completed_at: null,
  skipped_at: null,
  created_at: "2026-09-18T08:00:00+09:00",
  updated_at: "2026-09-18T08:00:00+09:00",
};
const photoRecord = {
  id: "018f7f00-7777-7777-8777-777777777777",
  child_id: child.id,
  photo_asset_ids: ["018f7f00-aaaa-7aaa-8aaa-aaaaaaaaaaaa"],
  user_context: "공원에서 잎을 관찰함",
  generated_observation: "여러 잎의 모양을 비교하며 차이를 설명했습니다.",
  generation_mode: "manual",
  status: "draft",
  job_id: null,
  error_message: null,
  suggested_tags: ["자연"],
  suggested_experience_axes: ["thinking_inquiry"],
  suggested_interest: "식물",
  suggested_difficulty_note: null,
  suggested_next_activity: "잎 분류표 만들기",
  learning_log_id: null,
  created_at: "2026-09-18T11:00:00+09:00",
  updated_at: "2026-09-18T11:00:00+09:00",
};
const conversation = {
  id: "018f7f00-8888-7888-8888-888888888888",
  child_id: child.id,
  title: "최근 자연 관찰",
  turns: [
    { role: "user", content: "최근 자연 관련 기록을 알려줘", source_ids: [], created_at: "2026-09-18T12:00:00+09:00" },
    { role: "assistant", content: "최근에는 잎의 모양을 비교한 기록이 있습니다.", source_ids: [log.id], created_at: "2026-09-18T12:00:10+09:00" },
  ],
  created_at: "2026-09-18T12:00:00+09:00",
  updated_at: "2026-09-18T12:00:10+09:00",
};
const growth = {
  child_id: child.id,
  period_days: 30,
  stage: child.stage,
  total_logs_in_period: 6,
  tagged_logs_in_period: 5,
  axes: [
    { axis: "thinking_inquiry", state: "최근 자주 경험함", observation_count: 3 },
    { axis: "reading", state: "다양하게 경험 중", observation_count: 2 },
    { axis: "speaking", state: "새롭게 나타난 관심", observation_count: 2 },
  ],
  layers: [
    { key: "whole_person", label: "전인 경험", axes: [{ axis: "social", state: "다양하게 경험 중", observation_count: 1 }] },
    { key: "learning", label: "학습 경험", axes: [{ axis: "thinking_inquiry", state: "최근 자주 경험함", observation_count: 3 }] },
    { key: "stage_focus", label: "단계 초점", axes: [{ axis: "reading", state: "다양하게 경험 중", observation_count: 2 }] },
  ],
  diversity: {
    state: "varied",
    observed_axis_count: 5,
    focus_axes: ["thinking_inquiry", "reading"],
    note: "여러 경험 축이 고르게 관찰됩니다.",
  },
};
const avatarAsset = {
  asset: {
    id: child.avatar_asset_id,
    child_id: child.id,
    original_filename: "avatar.png",
    mime_type: "image/png",
    relative_path: "photos/avatar.png",
    sha256: "synthetic",
    byte_size: 68,
    width: 1,
    height: 1,
    captured_at: null,
    metadata_summary: {},
    caption: null,
    caption_model: null,
  },
  data_base64: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
};

const mockSource = `
(() => {
  const fixtures = ${JSON.stringify({
    child, sibling, log, resource, material, activity, photoRecord, conversation, growth, avatarAsset,
  })};
  const clone = (value) => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  const responses = {
    core_health: {
      status: "ok",
      operation_mode: "core_only",
      core_requires_llm: false,
      llm_configured: true,
      llm_reachable: false,
      llm_features_enabled: false,
      embedding_features_enabled: false,
      model_provider: "ollama",
    },
    core_runtime_status: { started_by_desktop: true },
    list_children: [fixtures.child, fixtures.sibling],
    get_growth_map: fixtures.growth,
    list_observations: [fixtures.log],
    list_learning_records: [fixtures.log],
    list_resources: [fixtures.resource],
    list_materials: [fixtures.material],
    list_activities: [fixtures.activity],
    list_activity_observations: [fixtures.log],
    list_photo_records: [fixtures.photoRecord],
    get_photo_asset: fixtures.avatarAsset,
    list_conversations: [fixtures.conversation],
    list_backups: [{
      archive: "growwise-e2e.zip",
      path: "/tmp/growwise-e2e.zip",
      size_bytes: 4096,
      modified_at: "2026-09-18T13:00:00+09:00",
    }],
    list_material_results: [],
    get_entity_backlinks: { incoming: [], outgoing: [] },
    get_infant_activities: { suggestions: [] },
    get_infant_observation_hints: {
      source: "synthetic",
      effective_date: "2026-09-01",
      diagnostic: false,
      hints: [],
    },
    get_board_book_recommendations: { recommendations: [] },
    search_child_context: {
      query: "자연",
      plan: { keywords: ["자연"], entity_types: ["learning_log"], limit: 8 },
      results: [fixtures.log],
    },
  };
  globalThis.__GROWWISE_E2E_INVOKES__ = [];
  globalThis.__TAURI_INTERNALS__ = {
    invoke: async (command, args) => {
      globalThis.__GROWWISE_E2E_INVOKES__.push({ command, args: clone(args ?? {}) });
      if (Object.prototype.hasOwnProperty.call(responses, command)) return clone(responses[command]);
      if (command === "create_conversation") return clone(fixtures.conversation);
      if (command === "append_conversation_turn") {
        return {
          session_id: fixtures.conversation.id,
          thread_id: "e2e-thread",
          answer: { answer: "합성 답변입니다.", source_ids: [fixtures.log.id], insufficient_evidence: false },
          turn_count: 3,
        };
      }
      if (command === "transition_activity") return clone(fixtures.activity);
      if (command === "review_material" || command === "edit_material" || command === "revise_material_background") return clone(fixtures.material);
      if (command === "update_child" || command === "set_child_avatar" || command === "delete_child_avatar") return clone(fixtures.child);
      if (command.startsWith("create_") || command.startsWith("generate_") || command.startsWith("record_")) {
        throw new Error("E2E mock does not perform destructive mutations: " + command);
      }
      throw new Error("Unhandled E2E Tauri command: " + command);
    },
  };
})();
`;

async function evaluate(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "browser evaluation failed");
  }
  return result.result?.value;
}

async function waitForWorkspace(cdp, view) {
  await waitFor(
    async () => evaluate(
      cdp,
      `document.querySelector("#workspace-panel")?.dataset.activeWorkspace === ${JSON.stringify(view)}`,
    ),
    { label: `workspace ${view}` },
  );
  await new Promise((resolveWait) => setTimeout(resolveWait, 180));
}

async function assertLayoutHealth(cdp, view) {
  const result = await evaluate(cdp, `(() => {
    const root = document.querySelector(".workspace-shell-root");
    const panel = document.querySelector("#workspace-panel");
    if (!root || !panel) return { ok: false, reason: "missing shell" };
    const rootRect = root.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const interactive = [...document.querySelectorAll("button, input, select, textarea, a[href]")]
      .filter((node) => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
      });
    const offscreen = interactive.filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.right < -1 || rect.left > innerWidth + 1 || rect.bottom < -1 || rect.top > innerHeight + 1;
    }).length;
    return {
      ok: overflow <= 1 && offscreen === 0 && rootRect.width <= 1541 && panelRect.width > 0,
      overflow,
      offscreen,
      rootWidth: rootRect.width,
      panelWidth: panelRect.width,
      invokeCount: globalThis.__GROWWISE_E2E_INVOKES__?.length ?? -1,
      bodyText: document.body.innerText.slice(0, 5000),
    };
  })()`);
  invariant(result.ok, `${view}: layout health failed: ${JSON.stringify(result)}`);
  invariant(result.bodyText.includes({
    home: "대시보드",
    profile: "아이 프로필",
    learning: "학습 기록",
    materials: "자료실",
    photos: "사진첩",
    conversation: "대화하기",
    backup: "백업 및 복원",
    settings: "설정",
    help: "도움말",
  }[view]), `${view}: expected heading is not visible`);
}

async function screenshot(cdp, name) {
  const shot = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  const { mkdirSync, writeFileSync } = await import("node:fs");
  mkdirSync(ARTIFACTS, { recursive: true });
  writeFileSync(join(ARTIFACTS, `${name}.png`), Buffer.from(shot.data, "base64"));
}

async function main() {
  const server = await startStaticServer();
  const userDataDir = mkdtempSync(join(tmpdir(), "growwise-chrome-"));
  const chrome = spawn(findChrome(), [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--hide-scrollbars",
    `--remote-debugging-port=${DEBUG_PORT}`,
    "--remote-debugging-address=127.0.0.1",
    `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
    `--user-data-dir=${userDataDir}`,
    "about:blank",
  ], { stdio: ["ignore", "pipe", "pipe"] });

  let cdp;
  try {
    const target = await waitFor(async () => {
      const response = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
      if (!response.ok) return null;
      const targets = await response.json();
      return targets.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
    }, { label: "Chrome DevTools target" });

    cdp = new Cdp(target.webSocketDebuggerUrl);
    await cdp.connect();
    const browserErrors = [];
    cdp.on("Runtime.exceptionThrown", (params) => browserErrors.push(params.exceptionDetails?.text ?? "runtime exception"));
    cdp.on("Runtime.consoleAPICalled", (params) => {
      if (params.type === "error") {
        browserErrors.push(params.args?.map((item) => item.value ?? item.description).join(" ") || "console.error");
      }
    });

    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: VIEWPORT.width,
      height: VIEWPORT.height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: mockSource });
    await cdp.send("Page.navigate", { url: BASE_URL });
    await waitFor(
      async () => evaluate(cdp, 'document.readyState === "complete" && !!document.querySelector(".workspace-shell-root")'),
      { label: "GrowWise production shell" },
    );
    await waitForWorkspace(cdp, "home");

    const views = ["home", "profile", "learning", "materials", "photos", "conversation", "backup", "settings", "help"];
    const visualViews = new Set(["home", "profile", "learning", "materials", "conversation"]);
    for (const view of views) {
      if (view !== "home") {
        await evaluate(cdp, `document.querySelector("#workspace-nav-${view}")?.click(); true`);
        await waitForWorkspace(cdp, view);
      }
      await assertLayoutHealth(cdp, view);
      if (visualViews.has(view)) await screenshot(cdp, view);
    }

    // Global search affordance and Ctrl/Cmd+K must both enter Conversation.
    await evaluate(cdp, 'document.querySelector("#workspace-nav-home")?.click(); true');
    await waitForWorkspace(cdp, "home");
    await evaluate(cdp, 'document.querySelector(".workspace-search-trigger")?.click(); true');
    await waitForWorkspace(cdp, "conversation");

    await evaluate(cdp, 'document.querySelector("#workspace-nav-home")?.click(); true');
    await waitForWorkspace(cdp, "home");
    await evaluate(cdp, 'window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true })); true');
    await waitForWorkspace(cdp, "conversation");

    // Responsive contract: representative dense workspaces must collapse without horizontal overflow.
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 820,
      height: 1180,
      deviceScaleFactor: 1,
      mobile: false,
    });
    for (const view of ["learning", "materials", "conversation", "photos"]) {
      await evaluate(cdp, `document.querySelector("#workspace-nav-${view}")?.click(); true`);
      await waitForWorkspace(cdp, view);
      await assertLayoutHealth(cdp, view);
    }

    const unhandled = await evaluate(cdp, `globalThis.__GROWWISE_E2E_INVOKES__
      .filter((item) => !item.command)
      .length`);
    invariant(unhandled === 0, "browser invoke audit contained malformed entries");
    invariant(browserErrors.length === 0, `browser errors detected: ${browserErrors.join(" | ")}`);

    console.log("GrowWise browser E2E passed: 9 workspaces, shortcuts, desktop screenshots, responsive overflow.");
  } finally {
    cdp?.close();
    chrome.kill("SIGTERM");
    server.close();
    rmSync(userDataDir, { recursive: true, force: true });
  }
}

await main();
