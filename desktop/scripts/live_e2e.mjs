// Actual production UI + authenticated Core, with only the native IPC transport replaced.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { Cdp, evaluate, findChrome, startStaticServer, waitFor, waitForWorkspace } from "./browser_e2e.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
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
    const response = await fetch("/__e2e/core" + path, {
      method, headers: {"Content-Type":"application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(result));
    return result;
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
    if (Object.hasOwn(read, command)) return request(read[command]);
    if (command === "create_child") return request("/v1/children", "POST", a.request);
    if (command === "create_learning_record") return request("/v1/children/"+child+"/learning-records", "POST", a.request);
    if (command === "create_activity") return request("/v1/children/"+child+"/activities", "POST", {title:a.title,source_refs:a.sourceRefs,parent_note:null});
    if (command === "transition_activity") return request("/v1/activities/"+encodeURIComponent(a.activityId)+"/transition", "POST", {status:a.status,parent_note:a.parentNote??null});
    if (command === "list_activity_observations") return request("/v1/activities/"+encodeURIComponent(a.activityId)+"/observations");
    if (command === "create_resource") return request("/v1/resources", "POST", a.request);
    if (command === "update_resource") return request("/v1/resources/"+encodeURIComponent(a.resourceId)+"?acting_child_id="+encodeURIComponent(a.actingChildId), "PUT", a.request);
    if (command === "delete_resource") return request("/v1/resources/"+encodeURIComponent(a.resourceId)+"?acting_child_id="+encodeURIComponent(a.actingChildId), "DELETE");
    if (command === "create_photo_record") return request("/v1/children/"+child+"/photo-records", "POST", {files:a.files,user_context:a.userContext,manual_observation:a.manualObservation,ai_assist:a.aiAssist,shared_child_ids:a.sharedChildIds});
    if (command === "get_photo_asset") return request("/v1/children/"+child+"/photo-assets/"+encodeURIComponent(a.assetId));
    if (command === "commit_photo_record") return request("/v1/photo-records/"+encodeURIComponent(a.recordId)+"/commit", "POST", {observation:a.observation});
    if (command === "create_observation_background") return request("/v1/observations/background", "POST", a.request);
    if (command === "generate_material_background") return request("/v1/children/"+child+"/materials/background", "POST", {kind:a.kind,topic:a.topic,goal:a.goal,source_refs:a.sourceRefs});
    if (command === "use_material") return request("/v1/materials/"+material+"/use", "POST");
    if (command === "record_material_result") return request("/v1/materials/"+material+"/results", "POST", a.request);
    if (command === "create_conversation") return request("/v1/children/"+child+"/conversations", "POST", {});
    if (command === "delete_conversation") return request("/v1/conversations/"+encodeURIComponent(a.sessionId), "DELETE");
    if (command === "append_conversation_turn") return request("/v1/conversations/"+encodeURIComponent(a.sessionId)+"/turns", "POST", {question:a.question,limit:8});
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
  await waitFor(()=>evaluate(cdp,`(() => { const field=document.querySelector(${JSON.stringify(selector)}); return !!field && !field.disabled && field.getBoundingClientRect().height > 0; })()`),{label:`ready field ${selector}`});
  await evaluate(cdp, `(() => {
    const input = document.querySelector(${JSON.stringify(selector)});
    if (!input || input.disabled) throw new Error("field missing or disabled: " + ${JSON.stringify(selector)});
    const prototype = input.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype
      : input.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(input, ${JSON.stringify(value)});
    input.dispatchEvent(new Event("input", {bubbles:true}));
    input.dispatchEvent(new Event("change", {bubbles:true}));
  })()`);
}

async function clickText(text, selector = "button") {
  await waitFor(async () => evaluate(cdp, `(() => {
    const button = [...document.querySelectorAll(${JSON.stringify(selector)})].find((node) => (node.textContent.trim() === ${JSON.stringify(text)} || node.querySelector("strong")?.textContent.trim() === ${JSON.stringify(text)}) && node.getBoundingClientRect().height > 0 && !node.disabled);
    if (!button) return false; button.click(); return true;
  })()`), {label:`click ${text}`});
}

async function navigate(view) {
  await evaluate(cdp, `document.querySelector("#workspace-nav-${view}").click()`);
  await waitForWorkspace(cdp, view);
}

async function capture(name, selector) {
  if(selector) await evaluate(cdp,`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block:"center"})`);
  const image = await cdp.send("Page.captureScreenshot", {format:"png",captureBeyondViewport:false});
  writeFileSync(join(artifacts, `${name}.png`), Buffer.from(image.data,"base64"));
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
  await navigate("profile");
  await waitFor(()=>evaluate(cdp,'!!document.querySelector(".profile-form input:not(:disabled)")'),{label:"profile form"});
  await fill('.profile-form input[placeholder="예: 샘플아이"]',"가상실사용아이");
  await fill('.profile-form input[type="date"]',"2018-04-15");
  await clickText("첫 프로필 저장");
  await waitForWorkspace(cdp,"materials");
  const children = await api("/v1/children");
  assert.equal(children.length,1);
  const childId = children[0].id;
  assert.equal(children[0].stage,"elementary");
  steps.push("UI first-run profile persists and enters materials");

  await waitFor(()=>evaluate(cdp,'!!document.querySelector(".material-composer input:not(:disabled)")'),{label:"material composer"});
  await fill(".material-topic-field input","민들레 씨앗 관찰");
  await evaluate(cdp,'document.querySelector(".material-composer").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/materials`)).length === 1,{label:"saved generated material"});
  await clickText("이 활동 사용하기");
  await waitFor(async()=> (await api(`/v1/children/${childId}/materials`))[0].status === "approved",{label:"explicit parent approval"});
  const material = (await api(`/v1/children/${childId}/materials`))[0];
  steps.push("UI background generation saves template; explicit use passes real review gate");
  await clickText("활동 결과 기록");
  await fill(".material-result-panel textarea","민들레 씨앗을 보고 왜 날아가는지 질문했다.");
  await evaluate(cdp,'document.querySelector(".material-result-panel").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/materials/${material.id}/results`)).some((item)=>item.learning_logs.some((log)=>log.parent_observation.includes("민들레 씨앗을 보고"))),{label:"one-line result persisted"});
  const resultLog=(await api(`/v1/materials/${material.id}/results`))[0].learning_logs[0];
  await waitFor(()=>evaluate(cdp,'document.querySelector(".material-quest-meta")?.innerText.includes("민들레")'),{label:"saved material result visible"});
  await capture("material-used-and-recorded",".material-quest");
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
  await evaluate(cdp,'document.querySelector(".learning-record-form").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/children/${childId}/learning-records`)).length === 1,{label:"independent reading record saved through UI"});
  await waitFor(()=>evaluate(cdp,'document.querySelector(".learning-master-list")?.innerText.includes("씨앗 그림책 읽기")'),{label:"reading record appears in independent list"});
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
  await evaluate(cdp,'document.querySelector(".resource-form").requestSubmit()');
  await waitFor(async()=> (await api(`/v1/resources?child_id=${childId}`)).some((item)=>item.title === "민들레 참고 메모"),{label:"resource UI create"});
  await clickText("편집",".resource-card button");
  await fill(".resource-edit-panel input","민들레 참고 메모 수정");
  await clickText("수정 저장");
  await waitFor(async()=> (await api(`/v1/resources?child_id=${childId}`)).some((item)=>item.title === "민들레 참고 메모 수정"),{label:"resource UI update"});
  await clickText("상세",".resource-card button");
  await capture("resource-created-and-edited");
  await clickText("삭제",".resource-card button");
  await clickText("자료 삭제",'[role="alertdialog"] button');
  await waitFor(async()=> (await api(`/v1/resources?child_id=${childId}`)).length === 0,{label:"confirmed resource deletion"});
  steps.push("UI reference library create/edit/detail/confirmed delete reaches real Core");

  await navigate("photos");
  await evaluate(cdp,'(() => { const details=document.querySelector(".photo-create-summary").closest("details"); if(!details.open) details.querySelector("summary").click(); })()');
  const photoFile=join(temporary,"synthetic-activity.png");
  writeFileSync(photoFile,Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=","base64"));
  const dom=await cdp.send("DOM.getDocument");
  const fileInput=await cdp.send("DOM.querySelector",{nodeId:dom.root.nodeId,selector:'.photo-workspace input[type="file"]'});
  await cdp.send("DOM.setFileInputFiles",{nodeId:fileInput.nodeId,files:[photoFile]});
  await fill('.photo-workspace textarea[placeholder^="예: 오늘 둘이"]',"사진을 보며 씨앗 모양을 비교했다.");
  await evaluate(cdp,`[...document.querySelectorAll('.photo-workspace input[type="checkbox"]')].find(input=>input.closest('label').innerText.includes('로컬 AI')).click()`);
  await clickText("사진 일기 저장");
  await waitFor(async()=> (await api(`/v1/children/${childId}/photo-records`)).some((item)=>item.status === "draft"),{label:"photo uploaded as manual reviewable draft"});
  await clickText("확인하고 관찰 기록으로 저장");
  await waitFor(async()=> (await api(`/v1/children/${childId}/photo-records`))[0]?.status === "committed",{label:"photo parent confirmation persisted"});
  await waitFor(()=>evaluate(cdp,'[...document.querySelectorAll(".photo-gallery-thumb img")].some(image=>image.complete && image.naturalWidth > 0)'),{label:"real saved photo asset displayed"});
  await capture("manual-photo-record");
  steps.push("UI actual PNG upload, manual draft, parent confirmation and saved asset rendering pass");

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
  assert.deepEqual(await evaluate(cdp,"globalThis.__LIVE_TRANSPORT_ERRORS__ ?? []"),[]);
  assert.deepEqual(errors,[]);
  const buildAssets=await evaluate(cdp,'[...document.querySelectorAll("script[src],link[rel=stylesheet]")].map(element=>element.getAttribute("src")??element.getAttribute("href"))');
  const report={passed:true,transport:"browser IPC adapter -> authenticated actual Core; native runtime checked separately",llm:false,fixture:"synthetic children, observations and one-pixel PNG; isolated temporary data directory",buildAssets,steps,artifacts};
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
