// Actual production UI + authenticated Core, with only the native IPC transport replaced.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { Cdp, evaluate, evaluateWithArguments, findChrome, startStaticServer, waitFor, waitForWorkspace } from "./browser_e2e.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
function fingerprintCoreSource() {
  const directory=join(root,"src/growwise");
  const files=readdirSync(directory,{recursive:true}).filter(name=>name.endsWith(".py")).sort();
  const hash=createHash("sha256");
  for(const name of files) hash.update(name.replaceAll("\\","/")).update("\0").update(readFileSync(join(directory,name)));
  return hash.digest("hex");
}
const coreSourceSha256 = fingerprintCoreSource();
const desktopVersion = JSON.parse(readFileSync(new URL("../package.json", import.meta.url))).version;
const scriptSha256 = createHash("sha256").update(readFileSync(fileURLToPath(import.meta.url))).digest("hex");
const browserHelperSha256 = createHash("sha256").update(readFileSync(new URL("./browser_e2e.mjs", import.meta.url))).digest("hex");
const nativeCsp = JSON.parse(readFileSync(join(root,"desktop/src-tauri/tauri.conf.json"),"utf8")).app.security.csp;
const temporary = mkdtempSync(join(tmpdir(), "growwise-live-e2e-"));
const dataDir = join(temporary, "data");
const artifacts = process.env.GROWWISE_E2E_ARTIFACTS ?? join(temporary, "artifacts");
mkdirSync(artifacts, { recursive: true });
const token = randomBytes(32).toString("hex");
const portServer = createServer();
await new Promise((resolve, reject) => { portServer.once("error", reject); portServer.listen(0, "127.0.0.1", resolve); });
const port = portServer.address().port;
await new Promise((resolve) => portServer.close(resolve));
const coreUrl = `http://127.0.0.1:${port}`;
const python = process.env.GROWWISE_E2E_PYTHON
  ?? join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const core = spawn(python, ["-m", "growwise.api.secure_entry"], {
  cwd: root,
  env: {
    ...process.env,
    GROWWISE_DATA_DIR: dataDir,
    GROWWISE_API_HOST: "127.0.0.1",
    GROWWISE_API_PORT: String(port),
    GROWWISE_SESSION_TOKEN: token,
    GROWWISE_LLM_FEATURES_ENABLED: "false",
    GROWWISE_EMBEDDING_FEATURES_ENABLED: "false",
    GROWWISE_VISION_FEATURES_ENABLED: "false",
    GROWWISE_PUBLIC_ENRICHMENT_ENABLED: "false",
  },
  stdio: ["ignore", "ignore", "pipe"],
});
let coreErrors = "";
core.stderr.on("data", (chunk) => { coreErrors = (coreErrors + chunk).slice(-16000); });
core.on("error", (error) => { coreErrors += error.message; });
let server;
let chrome;
let cdp;
const errors = [];
const steps = [];

async function api(path, method = "GET", body) {
  const response = await fetch(`${coreUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  assert(response.ok, `${method} ${path}: ${JSON.stringify(result)}`);
  return result;
}

const transport = `(() => {
  const request = async (path, method = "GET", body) => {
    globalThis.__LIVE_INFLIGHT__ = (globalThis.__LIVE_INFLIGHT__ ?? 0) + 1;
    try {
    const response = await fetch("/__e2e/core" + path, {
      method, headers: {"Content-Type":"application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(result));
    return result;
    } finally { globalThis.__LIVE_INFLIGHT__ -= 1; }
  };
  globalThis.__TAURI_INTERNALS__ = { invoke: async (command, a = {}) => {
    try {
    const child = encodeURIComponent(a.childId ?? "");
    const material = encodeURIComponent(a.materialId ?? "");
    const read = {
      core_health: "/health",
      list_children: "/v1/children",
      get_growth_map: "/v1/children/" + child + "/growth-map",
      list_observations: "/v1/children/" + child + "/observations",
      list_learning_records: "/v1/children/" + child + "/learning-records",
      list_study_progress: "/v1/children/" + child + "/study/progress",
      list_study_mistakes: "/v1/children/" + child + "/study/mistakes",
      list_study_reflections: "/v1/children/" + child + "/study/reflections",
      list_self_explanations: "/v1/children/" + child + "/study/self-explanations",
      get_study_weak_map: "/v1/children/" + child + "/study/weak-map",
      list_study_plans: "/v1/children/" + child + "/study/plans",
      list_resources: "/v1/resources" + (child ? "?child_id=" + child : ""),
      list_materials: "/v1/children/" + child + "/materials",
      list_activities: "/v1/children/" + child + "/activities",
      list_photo_records: "/v1/children/" + child + "/photo-records",
      list_conversations: "/v1/children/" + child + "/conversations",
      list_backups: "/v1/admin/backups",
      list_material_results: "/v1/materials/" + material + "/results",
      get_learning_wiki: "/v1/children/" + child + "/learning-wiki",
      get_infant_activities: "/v1/children/" + child + "/infant-activities",
      get_infant_observation_hints: "/v1/children/" + child + "/infant-observation-hints",
      get_board_book_recommendations: "/v1/children/" + child + "/board-books",
    };
    if (command === "core_runtime_status") return {started_by_desktop:false};
    // Native release configuration is absent in this browser adapter; Core business data stays live.
    if (command === "app_update_status") return {configured:false,current_version:${JSON.stringify(desktopVersion)},checked:false,available_version:null,notes:null};
    if (Object.hasOwn(read, command)) {
      const result = await request(read[command]);
      // Delay only delivery of an actual authenticated Core response; never replace its data.
      const gate = Object.values(globalThis.__LIVE_RESPONSE_GATES__ ?? {}).find(
        item => item.command === command && item.childId === a.childId && !item.arrived,
      );
      if (gate) {
        gate.arrived = true;
        await new Promise(resolve => { gate.release = resolve; });
        gate.delivered = true;
      }
      return result;
    }
    if (command === "create_child") return request("/v1/children", "POST", a.request);
    if (command === "create_learning_record") return request("/v1/children/"+child+"/learning-records", "POST", a.request);
    if (command === "create_activity") return request("/v1/children/"+child+"/activities", "POST", {title:a.title,source_refs:a.sourceRefs,parent_note:null});
    if (command === "transition_activity") return request("/v1/activities/"+encodeURIComponent(a.activityId)+"/transition", "POST", {status:a.status,parent_note:a.parentNote??null});
    if (command === "list_activity_observations") return request("/v1/activities/"+encodeURIComponent(a.activityId)+"/observations");
    if (command === "create_resource") return request("/v1/resources", "POST", a.request);
    if (command === "update_resource") return request("/v1/resources/"+encodeURIComponent(a.resourceId)+"?acting_child_id="+encodeURIComponent(a.actingChildId), "PUT", a.request);
    if (command === "delete_resource") return request("/v1/resources/"+encodeURIComponent(a.resourceId)+"?acting_child_id="+encodeURIComponent(a.actingChildId), "DELETE");
    if (command === "create_photo_record") return request("/v1/children/"+child+"/photo-records", "POST", {files:a.files,user_context:a.userContext,manual_observation:a.manualObservation,ai_assist:a.aiAssist,shared_child_ids:a.sharedChildIds});
    if (command === "get_photo_asset" || command === "get_photo_thumbnail") {
      (globalThis.__LIVE_PHOTO_READS__ ??= []).push({command,childId:a.childId,assetId:a.assetId});
      return request("/v1/children/"+child+"/photo-assets/"+encodeURIComponent(a.assetId)+(command === "get_photo_thumbnail" ? "/thumbnail" : ""));
    }
    if (command === "commit_photo_record") return request("/v1/photo-records/"+encodeURIComponent(a.recordId)+"/commit", "POST", {observation:a.observation});
    if (command === "create_observation_background") return request("/v1/observations/background", "POST", a.request);
    if (command === "generate_material_background") return request("/v1/children/"+child+"/materials/background", "POST", {kind:a.kind,topic:a.topic,goal:a.goal,source_refs:a.sourceRefs});
    if (command === "use_material") return request("/v1/materials/"+material+"/use", "POST");
    if (command === "record_material_result") return request("/v1/materials/"+material+"/results", "POST", a.request);
    if (command === "create_conversation") return request("/v1/children/"+child+"/conversations", "POST", {});
    if (command === "delete_conversation") return request("/v1/conversations/"+encodeURIComponent(a.sessionId), "DELETE");
    if (command === "append_conversation_turn") return request("/v1/conversations/"+encodeURIComponent(a.sessionId)+"/turns", "POST", {question:a.question,limit:8});
    if (command === "get_conversation_evidence") return request("/v1/children/"+child+"/evidence?source_id="+encodeURIComponent(a.sourceId));
    if (command === "export_child_records") {
      const query=new URLSearchParams();
      if(a.startDate)query.set('start_date',a.startDate);
      if(a.endDate)query.set('end_date',a.endDate);
      const response=await fetch('/__e2e/core/v1/children/'+child+'/records/export?'+query);
      if(!response.ok)throw new Error(await response.text());
      const bytes=new Uint8Array(await response.arrayBuffer());
      globalThis.__LIVE_SELECTED_EXPORT__=btoa(Array.from(bytes,byte=>String.fromCharCode(byte)).join(''));
      return '/synthetic/selected-records.zip';
    }
    if (command === "search_child_context") return request("/v1/children/"+child+"/search?q="+encodeURIComponent(a.query));
    if (command === "get_entity_backlinks") return request("/v1/links/"+encodeURIComponent(a.entityId));
    if (command === "rebuild_learning_wiki") return request("/v1/children/"+child+"/learning-wiki/rebuild", "POST");
    if (command === "create_backup") return request("/v1/admin/backups", "POST", {});
    if (command === "restore_backup") return request("/v1/admin/backups/"+encodeURIComponent(a.archiveName)+"/restore", "POST", {confirmed:true});
    throw new Error("Live E2E has no native transport mapping for " + command);
    } catch (error) {
      (globalThis.__LIVE_TRANSPORT_ERRORS__ ??= []).push({command,error:String(error)});
      throw error;
    }
  }};
})();`;

async function fill(selector, value) {
  await waitFor(()=>evaluateWithArguments(cdp,(selector)=>{
    const field=document.querySelector(selector);
    return !!field && !field.disabled && field.getBoundingClientRect().height > 0;
  },selector),{label:`ready field ${selector}`});
  await evaluateWithArguments(cdp, (selector,value) => {
    const input = document.querySelector(selector);
    if (!input || input.disabled) throw new Error("field missing or disabled: " + selector);
    const prototype = input.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype
      : input.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(input, value);
    input.dispatchEvent(new Event("input", {bubbles:true}));
    input.dispatchEvent(new Event("change", {bubbles:true}));
  },selector,value);
}

async function clickText(text, selector = "button") {
  await waitFor(async () => evaluateWithArguments(cdp, (selector,text) => {
    const button = [...document.querySelectorAll(selector)].find((node) => (node.textContent.trim() === text || node.querySelector("strong")?.textContent.trim() === text) && node.getBoundingClientRect().height > 0 && !node.disabled);
    if (!button) return false; button.click(); return true;
  },selector,text), {label:`click ${text}`});
}

async function clickResourceAction(title, action) {
  await waitFor(()=>evaluateWithArguments(cdp,(title,action)=>{
    const card=[...document.querySelectorAll(".resource-card")]
      .find(node=>node.querySelector(".resource-card-heading strong")?.textContent === title);
    const button=card && [...card.querySelectorAll("button")]
      .find(node=>node.textContent.trim() === action && !node.disabled);
    if(!button || button.getBoundingClientRect().height === 0) return false;
    button.click();return true;
  },title,action),{label:`${action} on ${title}`});
}

async function fillLabel(context, text, value) {
  await waitFor(() => evaluateWithArguments(cdp, (context,text,value) => {
    const label=[...document.querySelectorAll(context + ' label')]
      .find(node=>node.querySelector('span')?.textContent.trim() === text);
    const input=label?.querySelector('input,textarea,select');
    if(!input || input.disabled || input.getBoundingClientRect().height === 0) return false;
    const proto=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype
      :input.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(input,value);
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true})); return true;
  },context,text,value),{label:`fill ${text}`});
}

async function navigate(view) {
  await evaluate(cdp, `document.querySelector("#workspace-nav-${view}").click()`);
  await waitForWorkspace(cdp, view);
}

async function verifyNavigationSoak(childId) {
  const seconds = Number(process.env.GROWWISE_E2E_SOAK_SECONDS ?? 0);
  assert(Number.isFinite(seconds) && seconds >= 0 && seconds <= 3600, "invalid soak duration");
  if (!seconds) return null;
  const seededRecords = Number(process.env.GROWWISE_E2E_SOAK_RECORDS ?? 1000);
  assert(Number.isInteger(seededRecords) && seededRecords >= 0 && seededRecords <= 5000, "invalid soak dataset");
  let nextRecord = 0;
  await Promise.all(Array.from({length:4}, async () => {
    while (nextRecord < seededRecords) {
      const number = nextRecord++;
      await api(`/v1/children/${childId}/learning-records`, "POST", {
        kind:"other", title:`장기 사용 합성 기록 ${number}`,
        summary:"민들레 씨앗의 모양과 움직임을 함께 살펴본 가상 관찰입니다. ".repeat(4),
        experience_axes:["exploration"],
        occurred_at:new Date(Date.now() - (number % 365) * 86400000).toISOString(),
      });
    }
  }));
  const views = ["home", "profile", "learning", "materials", "photos", "conversation", "backup", "help"];
  await fill(".workspace-child-picker select", childId);
  const cycle = async () => {
    for (const view of views) {
      await navigate(view);
      await evaluate(cdp, "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))");
      await waitFor(() => evaluate(cdp, "(globalThis.__LIVE_INFLIGHT__ ?? 0) === 0"), {label:`settled ${view} requests`});
    }
    await navigate("home");
  };
  // Warm all mounted workspaces and caches before measuring growth.
  for (let index = 0; index < 3; index += 1) await cycle();
  await cdp.send("Performance.enable", {});
  const samples = [];
  const started = Date.now();
  let cycles = 0;
  const sample = async () => {
    await cdp.send("HeapProfiler.collectGarbage", {});
    const heap = await cdp.send("Runtime.getHeapUsage", {});
    const {metrics} = await cdp.send("Performance.getMetrics", {});
    const rss = spawnSync("ps", ["-o", "rss=", "-p", String(core.pid)], {encoding:"utf8", timeout:2000});
    const coreRssBytes = rss.status === 0 ? Number(rss.stdout.trim()) * 1024 : null;
    samples.push({elapsedSeconds:Math.round((Date.now()-started)/1000), cycles,
      heapUsedBytes:heap.usedSize, coreRssBytes,
      ...Object.fromEntries(metrics.filter(item=>["Nodes","Documents","JSEventListeners"].includes(item.name)).map(item=>[item.name,item.value]))});
    writeFileSync(join(artifacts,"navigation-soak.json"),JSON.stringify({requestedSeconds:seconds, seededRecords, views, samples},null,2));
  };
  await sample();
  while (Date.now() - started < seconds * 1000) {
    await cycle();
    cycles += 1;
    if (Date.now() - started >= samples.at(-1).elapsedSeconds * 1000 + 30_000) {
      await sample();
      console.log(`Navigation soak: ${cycles} cycles, ${samples.at(-1).elapsedSeconds}s`);
    }
  }
  await sample();
  assert(cycles > 0);
  assert(samples.at(-1).heapUsedBytes < samples[0].heapUsedBytes + 8 * 1024 * 1024,
    "post-GC browser heap grew beyond the bounded smoke allowance");
  const rss = samples.filter(item=>item.coreRssBytes !== null);
  if (rss.length > 1) assert(rss.at(-1).coreRssBytes < rss[0].coreRssBytes + 32 * 1024 * 1024,
    "Core RSS grew beyond the bounded smoke allowance");
  assert.deepEqual(await evaluate(cdp,"globalThis.__LIVE_TRANSPORT_ERRORS__ ?? []"),[]);
  steps.push(`actual Core/UI navigation soak: ${seededRecords} added records, ${cycles} cycles across ${views.length} workspaces, ${samples.at(-1).elapsedSeconds}s, bounded post-GC heap and Core RSS`);
  return {requestedSeconds:seconds, seededRecords, views, cycles, samples};
}

async function capture(name, selector) {
  if(selector) await evaluate(cdp,`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block:"center"})`);
  const image = await cdp.send("Page.captureScreenshot", {format:"png",captureBeyondViewport:false});
  writeFileSync(join(artifacts, `${name}.png`), Buffer.from(image.data,"base64"));
}

async function gateRealResponse(name, command, childId) {
  await evaluate(cdp, `(() => {
    globalThis.__LIVE_RESPONSE_GATES__ ??= {};
    globalThis.__LIVE_RESPONSE_GATES__[${JSON.stringify(name)}] = {
      command: ${JSON.stringify(command)}, childId: ${JSON.stringify(childId)}, arrived: false, delivered: false,
    };
  })()`);
}

async function releaseRealResponse(name) {
  await evaluate(cdp, `globalThis.__LIVE_RESPONSE_GATES__[${JSON.stringify(name)}].release()`);
  await waitFor(() => evaluate(cdp, `globalThis.__LIVE_RESPONSE_GATES__[${JSON.stringify(name)}].delivered`),
    { label: `deliver delayed real response ${name}` });
  await evaluate(cdp, "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))");
}

async function verifyPrimaryPrint(material, artifactPrefix = "") {
  assert.equal(await evaluate(cdp, 'document.querySelector(".material-workflow-admin").open'), false);
  const detailsBefore = await evaluate(cdp, '[...document.querySelectorAll(".material-workflow-admin, .material-workflow-admin details")].map(node => node.open)');
  await evaluate(cdp, `(() => {
    globalThis.__LIVE_ORIGINAL_PRINT__ = window.print;
    globalThis.__LIVE_PRINT_CALLS__ = 0;
    window.print = () => { globalThis.__LIVE_PRINT_CALLS__ += 1; };
  })()`);
  try {
    await clickText("인쇄 / PDF 내보내기", ".material-document-toolbar button");
    await waitFor(() => evaluate(cdp, "globalThis.__LIVE_PRINT_CALLS__ === 1"), {label:"primary action reaches native print surface"});
    const target = await evaluate(cdp, `(() => {
      const card = document.querySelector('[data-growwise-print-target="true"]');
      return {
        count: document.querySelectorAll('[data-growwise-print-target="true"]').length,
        id: card?.getAttribute('data-approved-material-id'), scope: document.body.getAttribute('data-growwise-print-scope'),
        adminOpen: document.querySelector('.material-workflow-admin').open,
        allTargetDetailsOpen: [...(card?.querySelectorAll('details') ?? [])].every(node => node.open),
      };
    })()`);
    assert.deepEqual(target, {count:1,id:material.id,scope:"single",adminOpen:true,allTargetDetailsOpen:true});
    await cdp.send("Emulation.setEmulatedMedia", {media:"print"});
    assert(await evaluate(cdp, `(() => {
      const card=document.querySelector('[data-growwise-print-target="true"]');
      return card && getComputedStyle(card).visibility === 'visible' && card.getBoundingClientRect().width > 0
        && [...card.querySelectorAll('.material-preview, .material-support-pages')].every(node => getComputedStyle(node).display !== 'none');
    })()`), "selected approved document and supporting content remain visible in print media");
    await capture(`${artifactPrefix}primary-approved-material-print`);
    const pdf = await cdp.send("Page.printToPDF", {printBackground:true,preferCSSPageSize:true});
    const bytes = Buffer.from(pdf.data,"base64");
    assert.equal(bytes.subarray(0,5).toString(),"%PDF-");
    assert(bytes.length > 10000,"real PDF contains rendered document and fonts");
    writeFileSync(join(artifacts,`${artifactPrefix}approved-material.pdf`),bytes);
  } finally {
    await cdp.send("Emulation.setEmulatedMedia", {media:"screen"});
    await evaluate(cdp, `(() => {
      window.dispatchEvent(new Event('afterprint'));
      window.print = globalThis.__LIVE_ORIGINAL_PRINT__;
    })()`);
  }
  assert.deepEqual(await evaluate(cdp, `({
    adminOpen:document.querySelector('.material-workflow-admin').open,
    targetCount:document.querySelectorAll('[data-growwise-print-target="true"]').length,
    scope:document.body.getAttribute('data-growwise-print-scope'),
  })`), {adminOpen:false,targetCount:0,scope:null});
  assert.deepEqual(await evaluate(cdp, '[...document.querySelectorAll(".material-workflow-admin, .material-workflow-admin details")].map(node => node.open)'), detailsBefore,
    "printing restores every previously closed or open detail, including supporting guides");
  steps.push("primary approved-material print opens required details, selects one document, renders a real PDF, restores collapsed UI after printing");
}

async function verifyDelayedChildIsolation() {
  const oldChild = await api("/v1/children","POST", {nickname:"지연응답 검증 A",stage:"middle",age_months:160});
  const currentChild = await api("/v1/children","POST", {nickname:"지연응답 검증 B",stage:"middle",age_months:168});
  const oldTitle = "이전 아이 지연 학습 기록";
  const currentTitle = "현재 아이 확인 학습 기록";
  for (const [child,title,unit] of [[oldChild,oldTitle,"이전 아이 단원"],[currentChild,currentTitle,"현재 아이 단원"]]) {
    await api(`/v1/children/${child.id}/learning-records`,"POST", {
      kind:"self_study",title,summary:`${title}의 원본 관찰`,
    });
    await api(`/v1/children/${child.id}/study/progress`,"POST", {
      subject:"수학",unit,state:"in_progress",note:`${title}의 진도 기록`,
    });
  }
  // Refresh real child profiles before staying in one workspace throughout A -> B switching.
  await cdp.send("Page.reload",{});
  await waitFor(()=>evaluate(cdp,'document.readyState === "complete" && !!document.querySelector(".workspace-shell-root")'),{label:"reload new synthetic child fixtures"});
  await navigate("learning");
  const picker = ".workspace-child-picker select";
  await waitFor(()=>evaluate(cdp,`[...document.querySelectorAll(${JSON.stringify(picker + " option")})].some(node=>node.value === ${JSON.stringify(currentChild.id)})`),{label:"current-child picker contains new real profiles"});
  await gateRealResponse("old-learning","list_learning_records",oldChild.id);
  await gateRealResponse("old-study","list_study_progress",oldChild.id);
  await fill(picker,oldChild.id);
  await waitFor(()=>evaluate(cdp,'globalThis.__LIVE_RESPONSE_GATES__["old-learning"].arrived && globalThis.__LIVE_RESPONSE_GATES__["old-study"].arrived'),{label:"old child's real learning and study responses are delayed"});
  await fill(picker,currentChild.id);
  const visibleContext = () => evaluate(cdp,`({
    selected:document.querySelector(${JSON.stringify(picker)})?.value,
    learning:document.querySelector('.learning-hub-records .learning-master-list')?.innerText ?? '',
    study:document.querySelector('.learning-hub-records .study-history-list')?.innerText ?? '',
  })`);
  await waitFor(async()=>{
    const view=await visibleContext();
    return view.selected === currentChild.id && view.learning.includes(currentTitle) && view.study.includes("현재 아이 단원");
  },{label:"new child's own learning and study responses are visible first"});
  const assertCurrentChild = async () => {
    const view=await visibleContext();
    assert.equal(view.selected,currentChild.id);
    assert(view.learning.includes(currentTitle));
    assert(!view.learning.includes(oldTitle),"late learning response must not overwrite the new child's records");
    assert(view.study.includes("현재 아이 단원"));
    assert(!view.study.includes("이전 아이 단원"),"late study response must not overwrite the new child's study history");
  };
  await releaseRealResponse("old-learning");
  await assertCurrentChild();
  await releaseRealResponse("old-study");
  await assertCurrentChild();
  await capture("delayed-previous-child-responses");
  steps.push("real Core learning/study responses from child A are deliberately delivered after child B loads; current-child records remain isolated");
}

try {
  await waitFor(async () => {
    if (core.exitCode !== null) throw new Error(`Core exited: ${coreErrors}`);
    try { return (await fetch(`${coreUrl}/health`, {headers:{Authorization:`Bearer ${token}`}})).ok; }
    catch { return false; }
  }, {timeoutMs:30000,label:"authenticated real Core startup"});
  assert.equal((await fetch(`${coreUrl}/health`)).status,401);
  steps.push("real Core starts and rejects unauthenticated access");
  server = await startStaticServer({url:coreUrl,token});
  const chromeDir = join(temporary,"chrome");
  chrome = spawn(findChrome(), ["--headless=new","--no-sandbox","--disable-dev-shm-usage","--remote-debugging-port=0",`--user-data-dir=${chromeDir}`,"about:blank"], {stdio:"ignore"});
  chrome.on("error", (error) => errors.push(error.message));
  const debugPort = await waitFor(() => {
    const file=join(chromeDir,"DevToolsActivePort");
    return existsSync(file) ? Number.parseInt(readFileSync(file,"utf8"),10) : null;
  }, {timeoutMs:30000,label:"Chrome DevTools"});
  const targets = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
  cdp = new Cdp(targets.find((target)=>target.type === "page").webSocketDebuggerUrl);
  await cdp.connect();
  cdp.on("Runtime.exceptionThrown", (event) => errors.push(event.exceptionDetails?.exception?.description ?? event.exceptionDetails?.text));
  cdp.on("Runtime.consoleAPICalled", (event) => { if(event.type === "error") errors.push(event.args.map((item)=>item.value ?? item.description).join(" ")); });
  await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await cdp.send("Page.addScriptToEvaluateOnNewDocument",{source:transport});
  await cdp.send("Page.navigate",{url:"http://127.0.0.1:4173"});
  await waitFor(()=>evaluate(cdp,'!!document.querySelector(".workspace-shell-root")'),{label:"production UI"});
  await waitForWorkspace(cdp,"home");
  await capture("first-empty-home");
  await clickText("프로필 입력으로 이동");
  await waitForWorkspace(cdp,"profile");
  await waitFor(()=>evaluate(cdp,'!!document.querySelector(".profile-form input:not(:disabled)")'),{label:"profile form"});
  await cdp.send("Emulation.setDeviceMetricsOverride",{width:860,height:620,deviceScaleFactor:1,mobile:false});
  assert(await evaluate(cdp, `(() => {
    const field=document.querySelector('.profile-form input');
    const save=document.querySelector('.profile-form button[type=submit]');
    return field.getBoundingClientRect().top >= 0 && save.getBoundingClientRect().bottom <= innerHeight
      && document.documentElement.scrollWidth <= innerWidth;
  })()`),"first profile fields and save remain visible at the desktop minimum viewport");
  await capture("first-profile-minimum-window");
  await cdp.send("Emulation.setDeviceMetricsOverride",{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await fill('.profile-form input[placeholder="예: 샘플아이"]',"가상실사용아이");
  await fill('.profile-form input[type="date"]',"2018-04-15");
  await clickText("첫 프로필 저장");
  await waitForWorkspace(cdp,"materials");
  const children = await api("/v1/children");
  assert.equal(children.length,1);
  const childId = children[0].id;
  assert.equal(children[0].stage,"elementary");
  steps.push("UI first-run profile persists and enters materials");
  const book=await api('/v1/resources','POST',{kind:'book',title:'씨앗 그림책',child_id:childId,
    content:'씨앗이 바람에 이동하는 모습을 관찰한다.',source_name:'합성 검증 자료',tags:['씨앗']});

  await waitFor(()=>evaluate(cdp,'!!document.querySelector(".material-composer input:not(:disabled)")'),{label:"material composer"});
  await fill(".material-topic-field input","민들레 씨앗 관찰");
  await evaluate(cdp,'document.querySelector(".material-composer").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/materials`)).length === 1,{label:"saved generated material"});
  await clickText("이 활동 사용하기");
  await waitFor(async()=> (await api(`/v1/children/${childId}/materials`))[0].status === "approved",{label:"explicit parent approval"});
  const material = (await api(`/v1/children/${childId}/materials`))[0];
  steps.push("UI background generation saves template; explicit use passes real review gate");
  await verifyPrimaryPrint(material);
  await clickText("활동 결과 기록");
  await fill(".material-result-panel textarea","민들레 씨앗을 보고 왜 날아가는지 질문했다.");
  await clickText("더 자세히 기록","summary");
  await fillLabel('.material-result-panel','함께 읽은 책',book.id);
  await fillLabel('.material-result-panel','AI가 준 힌트','씨앗의 날개를 다시 관찰해 보자.');
  await fillLabel('.material-result-panel','근거 확인 여부','false');
  await fillLabel('.material-result-panel','아이가 다시 설명한 내용','날개가 있어 바람을 타는 것 같다.');
  await capture('optional-learning-evidence-form','.material-result-panel .learning-evidence-fields');
  await evaluate(cdp,'document.querySelector(".material-result-panel").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/materials/${material.id}/results`)).some((item)=>item.learning_logs.some((log)=>log.parent_observation.includes("민들레 씨앗을 보고"))),{label:"one-line result persisted"});
  const resultLog=(await api(`/v1/materials/${material.id}/results`))[0].learning_logs[0];
  assert.equal(resultLog.book_id,book.id);
  assert.equal(resultLog.evidence_checked,false);
  assert.equal(resultLog.child_reexplanation,'날개가 있어 바람을 타는 것 같다.');
  await waitFor(()=>evaluate(cdp,'document.querySelector(".material-quest-meta")?.innerText.includes("민들레")'),{label:"saved material result visible"});
  await capture("material-used-and-recorded",".material-quest");
  await evaluate(cdp,'document.querySelector(".material-result-history").open=true');
  await waitFor(()=>evaluate(cdp,'document.querySelector(".material-result-history").innerText.includes("확인하지 않음")'),{label:"saved false evidence and book context remain readable"});
  await capture('saved-learning-evidence-history','.material-result-history');
  await evaluate(cdp,'document.querySelector(".material-result-history").open=false');
  steps.push("UI one-line result writes authoritative learning record");

  await fill(".material-topic-field input","달의 모양 관찰");
  await evaluate(cdp,'document.querySelector(".material-composer").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/materials`)).length === 2,{label:"second distinct material saved through UI"});
  const secondMaterial=(await api(`/v1/children/${childId}/materials`)).find((item)=>item.id !== material.id);
  assert(secondMaterial);
  const documentSelector='select[aria-label="학습 자료 선택"]';
  await fill(documentSelector,material.id);
  await waitFor(()=>evaluate(cdp,`document.querySelector(".material-document-toolbar h3")?.innerText === ${JSON.stringify(material.title)}`),{label:"first document selected in primary canvas"});
  const firstDocumentContent=await evaluate(cdp,'document.querySelector(".material-studio-pane").innerText');
  assert(firstDocumentContent.includes("민들레 씨앗 관찰"));
  await fill(documentSelector,secondMaterial.id);
  await waitFor(()=>evaluate(cdp,`document.querySelector(".material-document-toolbar h3")?.innerText === ${JSON.stringify(secondMaterial.title)} && document.querySelector(".material-studio-pane")?.innerText.includes("달의 모양 관찰")`),{label:"second document selection changes primary heading and content"});
  const secondDocumentContent=await evaluate(cdp,'document.querySelector(".material-studio-pane").innerText');
  assert.notEqual(secondDocumentContent,firstDocumentContent);
  await capture("primary-material-document-selector",".material-document-toolbar");
  await fill(documentSelector,material.id);
  await waitFor(()=>evaluate(cdp,`document.querySelector(".material-studio-pane")?.innerText === ${JSON.stringify(firstDocumentContent)}`),{label:"first document remains reachable after selecting another"});
  steps.push("UI creates two distinct materials and native selector changes primary document heading/content in both directions");

  await navigate("learning");
  await fill('.learning-record-form input[placeholder="예: 어린 왕자 독서감상"]',"씨앗 그림책 읽기");
  await fill('.learning-record-form textarea[placeholder="부모가 확인한 사실이나 아이가 설명한 내용을 기록하세요."]',"민들레 그림책을 읽고 씨앗이 이동하는 방법을 이야기했다.");
  await clickText('책과 AI 도움·근거를 더 기록하기(선택)','summary');
  await fillLabel('.learning-record-form','함께 읽은 책',book.id);
  await fillLabel('.learning-record-form','AI가 준 힌트','그림에서 같은 모양을 찾아보자.');
  await fillLabel('.learning-record-form','근거 확인 여부','true');
  await fillLabel('.learning-record-form','아이가 다시 설명한 내용','그림과 실제 씨앗의 모양이 닮았다.');
  await evaluate(cdp,'document.querySelector(".learning-record-form").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/learning-records`)).length === 1,{label:"independent reading record saved through UI"});
  await waitFor(()=>evaluate(cdp,'document.querySelector(".learning-master-list")?.innerText.includes("씨앗 그림책 읽기")'),{label:"reading record appears in independent list"});
  assert(await evaluate(cdp,'document.querySelector(".learning-detail-panel").innerText.includes("그림과 실제 씨앗의 모양이 닮았다.")'));
  await capture('independent-learning-evidence-detail','.learning-detail-panel .learning-evidence-details');
  steps.push("UI independent reading record preserves separate record kind");
  await clickText("관찰 기록",'[role="tab"]');
  await waitFor(()=>evaluate(cdp,'document.body.innerText.includes("민들레")'),{label:"activity result in learning records"});
  await capture("learning-records",".timeline-section");
  const wiki=await api(`/v1/children/${childId}/learning-wiki/rebuild`,"POST");
  assert(wiki.source_refs?.includes(`learning_log:${resultLog.id}`), JSON.stringify(wiki));
  await navigate("profile");
  await clickText("성장 리포트",'[role="tab"]');
  await waitFor(()=>evaluate(cdp,'document.querySelector(".learning-wiki-panel")?.innerText.includes("AI 없이")'),{label:"grounded Learning Wiki shown in actual profile UI"});
  await clickText("원본 기록에서 다시 정리");
  await waitFor(async()=> (await api(`/v1/children/${childId}/learning-wiki`)).revision > wiki.revision,{label:"explicit UI Learning Wiki rebuild"});
  await capture("profile-learning-wiki",".learning-wiki-panel");
  steps.push("UI profile Learning Wiki shows provenance-backed context and explicitly rebuilds from originals");
  await navigate("conversation");
  await fill(".conversation-composer input","민들레 씨앗을 보고 어떤 질문을 했어?");
  await evaluate(cdp,'document.querySelector(".conversation-composer").requestSubmit()');
  await waitFor(async()=>{
    const sessions=await api(`/v1/children/${childId}/conversations`);
    return sessions.some((session)=>session.turns?.some((turn)=>turn.role === "assistant" && turn.source_ids?.includes(`record:${resultLog.id}`)));
  },{label:"grounded conversation answer"});
  await capture("grounded-conversation");
  await evaluate(cdp,'document.querySelector(".conversation-original summary").click()');
  await waitFor(()=>evaluate(cdp,'document.querySelector(".conversation-original-content pre")?.innerText.includes("민들레")'),{label:"cited current original opens in conversation"});
  await capture("conversation-original-source",".conversation-original-content");
  steps.push("UI opens a cited current original with title, event date and body through child-scoped evidence resolution");
  steps.push("UI conversation retrieves real records with source refs; Learning Wiki grounded");
  const retainedConversation=(await api(`/v1/children/${childId}/conversations`))[0];
  await evaluate(cdp,'document.querySelector(".conversation-new-button").click()');
  await fill(".conversation-composer input","씨앗 그림책 기록");
  await evaluate(cdp,'document.querySelector(".conversation-composer").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/conversations`)).filter((session)=>session.turns.some((turn)=>turn.role === "assistant")).length === 2,{label:"second actual conversation saved"});
  await clickText("선택한 대화 삭제");
  await clickText("대화 삭제",'[role="alertdialog"] button');
  await waitFor(async()=> (await api(`/v1/children/${childId}/conversations`)).length === 1,{label:"UI confirmed conversation deletion"});
  assert.equal((await api(`/v1/children/${childId}/conversations`))[0].id,retainedConversation.id);
  assert((await api(`/v1/children/${childId}/observations`)).some((log)=>log.id === resultLog.id));
  steps.push("UI confirmed conversation deletion preserves another conversation and original source records");

  await clickText("기록을 직접 검색하기","summary");
  await fill(".search-form input","민들레");
  await evaluate(cdp,'document.querySelector(".search-form").requestSubmit()');
  await waitFor(()=>evaluate(cdp,'document.querySelectorAll(".search-result-card").length > 0'),{label:"real direct lexical search results"});
  const searchResult=await api(`/v1/children/${childId}/search?q=${encodeURIComponent("민들레")}`);
  assert(searchResult.results.length > 0);
  steps.push("UI direct search returns actual child-scoped records without an LLM");

  await navigate("materials");
  await clickText("참고 자료",'[role="tab"]');
  await fill(".resource-form input","민들레 참고 메모");
  await fill(".resource-form textarea","씨앗은 바람에 움직인다. 실제 산책에서 관찰할 질문을 남긴다.");
  await clickText('출처·분류 설정(선택)','.resource-form summary');
  await fillLabel('.resource-form','출처 이름','합성 자연 관찰 자료');
  await fillLabel('.resource-form','출처 URL','https://example.org/seed');
  await fillLabel('.resource-form','저자·작성자','합성 작성자');
  await fillLabel('.resource-form','태그','씨앗, 관찰');
  await fillLabel('.resource-form','사용 범위','shared');
  await evaluate(cdp,'document.querySelector(".resource-form").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/resources?child_id=${childId}`)).some((item)=>item.title === "민들레 참고 메모"),{label:"resource UI create"});
  const createdResource=(await api(`/v1/resources?child_id=${childId}`)).find(item=>item.title === "민들레 참고 메모");
  assert.deepEqual(createdResource.tags,['씨앗','관찰']);
  await clickResourceAction("민들레 참고 메모","편집");
  await fill(".resource-edit-panel input","민들레 참고 메모 수정");
  await clickText('출처·분류 설정(선택)','.resource-edit-panel summary');
  await fillLabel('.resource-edit-panel','출처 이름','출처 수정 검증');
  await fillLabel('.resource-edit-panel','사용 범위','child');
  await clickText("수정 저장");
  await waitFor(async()=> (await api(`/v1/resources?child_id=${childId}`)).some((item)=>item.title === "민들레 참고 메모 수정"),{label:"resource UI update"});
  const editedResource=(await api(`/v1/resources?child_id=${childId}`)).find(item=>item.title==='민들레 참고 메모 수정');
  assert.equal(editedResource.source_name,'출처 수정 검증');
  assert.equal(editedResource.child_id,childId);
  assert.deepEqual(editedResource.tags,['씨앗','관찰']);
  assert.equal(editedResource.id,createdResource.id);
  await clickResourceAction("민들레 참고 메모 수정","상세");
  await capture("resource-created-and-edited");
  await clickResourceAction("민들레 참고 메모 수정","삭제");
  await clickText("자료 삭제",'[role="alertdialog"] button');
  await waitFor(async()=> !(await api(`/v1/resources?child_id=${childId}`)).some(item=>item.id===editedResource.id),{label:"confirmed resource deletion"});
  steps.push("UI reference library create/edit/detail/confirmed delete reaches real Core");

  await navigate("conversation");
  await fill('.conversation-composer input','씨앗 그림책과 현재 관심사를 연결해 내일 할 활동을 만들어줘');
  await evaluate(cdp,'document.querySelector(".conversation-composer").requestSubmit()');
  await waitFor(()=>evaluate(cdp,'[...document.querySelectorAll(".conversation-turn button")].some(node=>node.textContent.trim()==="이 내용으로 활동 만들기")'),{label:"conversation offers explicit material action"});
  assert.equal((await api(`/v1/children/${childId}/materials`)).length,2,"a conversation proposal must not create a draft without parent action");
  await clickText('이 내용으로 활동 만들기','.conversation-turn button');
  await waitForWorkspace(cdp,'materials');
  await waitFor(()=>evaluate(cdp,'document.querySelector(".material-topic-field input")?.value.includes("씨앗 그림책")'),{label:"conversation topic reaches primary material composer"});
  assert(await evaluate(cdp,`[...document.querySelectorAll('.resource-grounding-picker input')].some(node=>node.checked && node.closest('label').innerText.includes(${JSON.stringify(book.title)}))`),"visible book source reaches material composer");
  await evaluate(cdp,'document.querySelector(".material-composer").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/materials`)).length === 3,{label:"explicit parent action creates a new material draft from conversation"});
  const commanded=(await api(`/v1/children/${childId}/materials`)).find(item=>item.id!==material.id&&item.id!==secondMaterial.id);
  assert.equal(commanded.kind,'reading_activity');
  assert.notEqual(commanded.status,'approved');
  assert(commanded.source_refs.includes(`resource:${book.id}`));
  steps.push("UI conversation proposal carries topic and visible book into composition; explicit parent generation saves an unapproved draft");

  await navigate("photos");
  await evaluate(cdp,'(() => { const details=document.querySelector(".photo-create-summary").closest("details"); if(!details.open) details.querySelector("summary").click(); })()');
  const photoFile=join(temporary,"synthetic-activity.png");
  const photoFixture=spawnSync(python,["-c","from PIL import Image; import sys; image=Image.new('RGB',(2048,1536),'#39745d'); image.save(sys.stdout.buffer,format='PNG'); image.close()"],{cwd:root});
  assert.equal(photoFixture.status,0,"create a real multi-megapixel synthetic PNG fixture");
  writeFileSync(photoFile,photoFixture.stdout);
  const dom=await cdp.send("DOM.getDocument");
  const fileInput=await cdp.send("DOM.querySelector",{nodeId:dom.root.nodeId,selector:'.photo-workspace input[type="file"]'});
  await cdp.send("DOM.setFileInputFiles",{nodeId:fileInput.nodeId,files:[photoFile]});
  await waitFor(()=>evaluate(cdp,'[...document.querySelectorAll(".photo-preview-grid img")].some(image=>image.complete && image.naturalWidth > 0)'),{label:"small local selected-photo preview"});
  const localPreview=await evaluate(cdp,`(()=>{
    const image=document.querySelector('.photo-preview-grid img');
    return {width:image.naturalWidth,height:image.naturalHeight,url:image.src};
  })()`);
  assert(localPreview.width<=384 && localPreview.height<=384,"selected photo preview must be resized before display");
  // Inspect the loaded image through trusted CDP; production CSP intentionally forbids fetch(blob:).
  const {frameTree}=await cdp.send("Page.getFrameTree",{});
  const previewResource=await cdp.send("Page.getResourceContent",{frameId:frameTree.frame.id,url:localPreview.url});
  assert(previewResource.base64Encoded);
  const previewBytes=Buffer.from(previewResource.content,"base64");
  assert.equal(previewBytes.subarray(0,2).toString("hex"),"ffd8");
  assert(previewBytes.length<=128*1024);
  await capture("selected-local-photo-preview");
  await fill('.photo-workspace textarea[placeholder^="예: 오늘 둘이"]',"사진을 보며 씨앗 모양을 비교했다.");
  await evaluate(cdp,`[...document.querySelectorAll('.photo-workspace input[type="checkbox"]')].find(input=>input.closest('label').innerText.includes('로컬 AI')).click()`);
  await clickText("사진 일기 저장");
  await waitFor(async()=> (await api(`/v1/children/${childId}/photo-records`)).some((item)=>item.status === "draft"),{label:"photo uploaded as manual reviewable draft"});
  await clickText("확인하고 관찰 기록으로 저장");
  await waitFor(async()=> (await api(`/v1/children/${childId}/photo-records`))[0]?.status === "committed",{label:"photo parent confirmation persisted"});
  await waitFor(()=>evaluate(cdp,'[...document.querySelectorAll(".photo-gallery-thumb img")].some(image=>image.complete && image.naturalWidth > 0)'),{label:"real saved photo asset displayed"});
  const savedPhoto=(await api(`/v1/children/${childId}/photo-records`))[0];
  const thumbnail=await api(`/v1/children/${childId}/photo-assets/${savedPhoto.photo_asset_ids[0]}/thumbnail`);
  const thumbnailBytes=Buffer.from(thumbnail.data_base64,"base64");
  assert.equal(thumbnail.mime_type,"image/jpeg");
  assert(thumbnail.width <= 384 && thumbnail.height <= 384);
  assert(thumbnailBytes.length <= 128*1024);
  assert(!thumbnailBytes.equals(readFileSync(photoFile)),"gallery derivative must not contain the original PNG bytes");
  const originalAfterThumbnail=await api(`/v1/children/${childId}/photo-assets/${savedPhoto.photo_asset_ids[0]}`);
  assert.equal(originalAfterThumbnail.data_base64,readFileSync(photoFile).toString("base64"));
  const browserPhotoReads=await evaluate(cdp,"globalThis.__LIVE_PHOTO_READS__ ?? []");
  assert(browserPhotoReads.some((read)=>read.command === "get_photo_thumbnail"));
  assert.equal(browserPhotoReads.filter((read)=>read.command === "get_photo_asset").length,0,"photo UI must use small previews instead of original downloads");
  await capture("manual-photo-record");
  steps.push("UI actual PNG upload, parent confirmation and bounded JPEG thumbnails pass; original PNG remains byte-identical and UI never fetches full originals");

  await navigate("profile");
  await clickText("아이 추가 · 사진 관리");
  await fill('.profile-form input[placeholder="예: 샘플아이"]',"둘째가상아이");
  await fill('.profile-form input[type="date"]',"2021-06-10");
  await evaluate(cdp,'document.querySelector(".profile-form").requestSubmit()');
  await waitFor(async()=> (await api("/v1/children")).length === 2,{label:"second child created through UI"});
  const second=(await api("/v1/children")).find((child)=>child.nickname === "둘째가상아이");
  assert(second);
  await clickText("← 프로필로 돌아가기");
  await fill(".profile-child-switcher select",second.id);
  await navigate("conversation");
  await clickText("기록을 직접 검색하기","summary");
  await fill(".search-form input","민들레");
  await evaluate(cdp,'document.querySelector(".search-form").requestSubmit()');
  await waitFor(()=>evaluate(cdp,'document.querySelector(".search-results")?.innerText.includes("검색 결과 0건")'),{label:"second child cannot see first child's private records"});
  assert.equal((await api(`/v1/children/${second.id}/observations`)).length,0);
  assert.equal((await api(`/v1/children/${second.id}/conversations`)).length,0);
  await capture("second-child-private-scope");
  await navigate("profile");
  await fill(".profile-child-switcher select",childId);
  await navigate("learning");
  await waitFor(()=>evaluate(cdp,'document.querySelector(".learning-master-list")?.innerText.includes("씨앗 그림책 읽기")'),{label:"switching back restores first-child context"});
  steps.push("UI creates second child, switches contexts, isolates private search/history, restores first-child view");

  await navigate("backup");
  await clickText("지금 백업");
  await waitFor(async()=> (await api("/v1/admin/backups")).length === 1,{label:"UI backup archive created"});
  const backup=(await api("/v1/admin/backups"))[0];
  const extra = await api("/v1/children","POST",{nickname:"복원확인용가상아이",stage:"preschool_3_5",age_months:48});
  assert(extra.id);
  await clickText("이 백업 복원",".quest-card button");
  await clickText("이 백업 복원",'[role="alertdialog"] button');
  await waitFor(async()=> (await api("/v1/children")).length === 2,{label:"confirmed UI restore applied"});
  assert.equal((await api("/v1/children")).length,2);
  assert.deepEqual((await api("/v1/children")).map((child)=>child.id).sort(),[childId,second.id].sort());
  assert.equal((await api(`/v1/materials/${material.id}/results`))[0].learning_logs[0].id,resultLog.id);
  assert.equal((await api(`/v1/children/${childId}/learning-records`)).length,1);
  const restoredPhoto=(await api(`/v1/children/${childId}/photo-records`))[0];
  assert.equal(restoredPhoto.status,"committed");
  const restoredAsset=await api(`/v1/children/${childId}/photo-assets/${restoredPhoto.photo_asset_ids[0]}`);
  assert.equal(restoredAsset.data_base64,readFileSync(photoFile).toString("base64"));
  const restoredSessions=await api(`/v1/children/${childId}/conversations`);
  assert(restoredSessions.some((session)=>session.turns.some((turn)=>turn.source_ids?.includes(`record:${resultLog.id}`))));
  assert.deepEqual(await evaluate(cdp,"globalThis.__LIVE_TRANSPORT_ERRORS__ ?? []"),[]);
  await cdp.send("Page.reload",{});
  await waitFor(()=>evaluate(cdp,'document.readyState === "complete" && !!document.querySelector(".workspace-shell-root")'),{label:"reload after restore"});
  await navigate("learning");
  await clickText("관찰 기록",'[role="tab"]');
  await waitFor(()=>evaluate(cdp,'document.body.innerText.includes("민들레")'),{label:"restored record visible"});
  await capture("restored-records",".timeline-section");
  steps.push("real backup/restore removes newer child, preserves material result/conversation, UI reloads");
  await verifyDelayedChildIsolation();

  const older=await api(`/v1/children/${childId}/learning-records`,'POST',{
    kind:'other',title:'기간 선택 검증용 기록',summary:'선택한 아이의 과거 원문 관찰',
    occurred_at:'2020-06-15T12:00:00Z',
  });
  await navigate('backup');
  await fill('.record-export-form select',childId);
  await fill('.record-export-form input[type=date]:nth-of-type(1)','2020-01-01');
  await fill('.record-export-form label:last-child input','2020-12-31');
  await clickText('선택 기록 내보내기');
  await waitFor(()=>evaluate(cdp,'Boolean(globalThis.__LIVE_SELECTED_EXPORT__)'),{label:'selected-period ZIP downloaded from real Core'});
  const selectedZip=join(artifacts,'selected-records.zip');
  writeFileSync(selectedZip,Buffer.from(await evaluate(cdp,'globalThis.__LIVE_SELECTED_EXPORT__'),'base64'));
  const zipCheck=spawnSync(python,['-c',`
import hashlib,json,sys,zipfile
from pathlib import Path
from growwise.backup.service import BackupService,InvalidBackup
with zipfile.ZipFile(sys.argv[1]) as archive:
 manifest=json.loads(archive.read('growwise-record-export.json'))
 assert manifest['child_id']==sys.argv[2] and manifest['start_date']=='2020-01-01' and manifest['end_date']=='2020-12-31'
 assert manifest['restorable_by_app'] is False
 names=archive.namelist()
 assert any(sys.argv[3] in name for name in names)
 assert not any(sys.argv[4] in name or sys.argv[5] in name for name in names)
 for name,digest in manifest['sha256'].items(): assert hashlib.sha256(archive.read(name)).hexdigest()==digest
try: BackupService().validate_archive(Path(sys.argv[1]))
except InvalidBackup: pass
else: raise AssertionError('selected export must not be accepted as a whole-app restore')
`,selectedZip,childId,older.id,resultLog.id,second.id],{cwd:root,encoding:'utf8'});
  assert.equal(zipCheck.status,0,zipCheck.stderr);
  await capture('selected-records-export','.record-export-section');
  steps.push('UI child/date raw Markdown export downloads a real hashed ZIP containing only the chosen period and child; full backup restore rejects it');

  const infant=await api('/v1/children','POST',{nickname:'영아 인쇄 검증',stage:'infant_0_2',age_months:9});
  const infantMaterial=await api(`/v1/children/${infant.id}/materials`,'POST',{kind:'activity_guide',topic:'소리와 움직임 살펴보기'});
  await api(`/v1/materials/${infantMaterial.id}/use`,'POST',{});
  infantMaterial.status='approved';
  await cdp.send('Page.reload',{});
  await waitFor(()=>evaluate(cdp,'Boolean(document.querySelector(".workspace-child-picker"))'),{label:'infant profile available'});
  await fill('.workspace-child-picker select',infant.id);
  await navigate('materials');
  await waitFor(()=>evaluate(cdp,`document.querySelector('.material-document-toolbar h3')?.innerText === ${JSON.stringify(infantMaterial.title)}`),{label:'infant activity visible'});
  assert.equal(await evaluate(cdp,'document.querySelectorAll(".material-presentation-template").length'),0);
  assert(await evaluate(cdp,'document.querySelector(".material-studio-pane").innerText.includes("활동 전 안전")'));
  await verifyPrimaryPrint(infantMaterial,'infant-');
  steps.push('infant activity preserves visible parent safety guidance and printable parent guide while excluding learner worksheets and writing spaces');
  const navigationSoak = await verifyNavigationSoak(childId);
  assert.equal(fingerprintCoreSource(),coreSourceSha256,"Core source changed during the run; repeat against frozen source");
  assert.equal(createHash("sha256").update(readFileSync(fileURLToPath(import.meta.url))).digest("hex"),scriptSha256,"live script changed during the run");
  assert.equal(createHash("sha256").update(readFileSync(new URL("./browser_e2e.mjs",import.meta.url))).digest("hex"),browserHelperSha256,"browser helper changed during the run");
  assert.deepEqual(await evaluate(cdp,"globalThis.__LIVE_TRANSPORT_ERRORS__ ?? []"),[]);
  assert.deepEqual(errors,[]);
  const buildAssets=await evaluate(cdp,'[...document.querySelectorAll("script[src],link[rel=stylesheet]")].map(element=>element.getAttribute("src")??element.getAttribute("href"))');
  const report={passed:true,transport:"browser IPC adapter -> authenticated actual Core; native runtime checked separately",llm:false,fixture:"synthetic children, observations and 2048x1536 PNG; isolated temporary data directory",scriptSha256,browserHelperSha256,coreSourceSha256,nativeCsp,buildAssets,steps,artifacts,navigationSoak};
  writeFileSync(join(artifacts,"report.json"),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
} catch(error) {
  if(cdp) { await capture("failure").catch(()=>{}); writeFileSync(join(artifacts,"failure-dom.txt"),String(await evaluate(cdp,"document.body.innerText").catch(()=>""))); }
  console.error(error,coreErrors,`Artifacts: ${artifacts}`);
  process.exitCode=1;
} finally {
  cdp?.close();
  for(const process of [chrome,core]) {
    if(process && process.exitCode === null) {
      process.kill("SIGTERM");
      await new Promise((resolve)=>{const timer=setTimeout(()=>{process.kill("SIGKILL");resolve();},4000);process.once("exit",()=>{clearTimeout(timer);resolve();});});
    }
  }
  if(server) await new Promise((resolve)=>server.close(resolve));
}
