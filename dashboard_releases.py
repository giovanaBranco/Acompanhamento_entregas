"""
Dashboard Release - Épicos, Features, User Stories e Tasks - DINÂMICO
============================================================
Mostra os Épicos de todas as releases (Custom.SR_RELEASE preenchido, com
qualquer valor e em qualquer área) e, no grupo "Sem release", os Épicos da
área do time ainda não encerrados (não Closed/Done/Removed) e sem release
informada. Para cada épico, exibe a hierarquia
completa: Épico -> Features -> User Stories (filhas da Feature) -> Tasks
(filhas da User Story), com contagem de status, percentual de conclusão,
filtro por Release/Area Path, comentários de acompanhamento (#acompanhamento)
e link para consulta no Azure DevOps.

Percentual de conclusão: itens (Feature, User Story/Bug e Task, todos com o
mesmo peso) em Closed/Done/Resolved dividido pelo total de itens. Itens
Removed aparecem na árvore, mas não entram nas contagens nem no percentual.

Os dados são buscados diretamente do Azure DevOps PELO NAVEGADOR, usando um
Personal Access Token salvo no localStorage (mesmo PAT usado nos demais
dashboards do portal). Não é necessário rodar este script sempre que os
dados mudarem — basta abrir o HTML e clicar em "Atualizar dados".

Uso:
    python dashboard_releases.py
"""

import json

from ado_common import render_page, write_html

OUTPUT_FILE = "dashboard_releases.html"

RELEASE_FIELD = "Custom.SR_RELEASE"
TRACKING_TAG = "#acompanhamento"
PRODUTO_OK_TAG = "produtoOK"
PRIORITY_FIELD = "Microsoft.VSTS.Common.Priority"    # 1 = maior ... 4 = baixa
DUE_DATE_FIELD = "Microsoft.VSTS.Scheduling.DueDate"  # prazo acordado

CSS = """
/* Prioridade (1 = maior ... 4 = baixa) e prazo acordado (Due Date) */
.prio { display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; font-size:0.68rem; font-weight:800; flex:0 0 auto; border:1.5px solid currentColor; }
.prio.p1 { color:#fff; background:#c62828; border-color:#c62828; }
.prio.p2 { color:#e65100; background:#fff3e0; }
.prio.p3 { color:#1565c0; background:#e3f2fd; }
.prio.p4 { color:#6b7280; background:#f3f4f6; }
.prio.p-none { color:var(--faint); border-style:dashed; font-weight:400; }
.due { font-size:0.76rem; color:var(--muted); white-space:nowrap; font-variant-numeric:tabular-nums; }
.due.soon { color:#e65100; font-weight:700; }
.due.late { color:#c62828; font-weight:700; }
.due.late::before { content:"⚠ "; }
.legend .prio { margin-right:3px; vertical-align:-4px; }
.legend + .legend { margin-top:-8px; }
/* KPIs: contagens ocupam o dobro do espaço */
.kpis { grid-template-columns:2fr 1fr 1fr; }
.pct { font-weight:800; font-size:1.05rem; min-width:60px; text-align:right; }
.pct.high { color:var(--done); }
.pct.mid { color:#e65100; }
.pct.low { color:var(--muted); }

/* Grupos por release */
.release-group { margin-bottom:22px; }
.release-head { display:flex; align-items:center; gap:14px; padding:0 20px 8px 4px; border-bottom:2px solid var(--line); margin-bottom:10px; }
.release-head h2 { font-size:1rem; color:var(--ink); }
.release-head .count { font-size:0.78rem; color:var(--muted); }

ul.epic-list { list-style:none; }

/* Card de épico */
li.epic-card { background:var(--card); border-radius:8px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06); border-left:4px solid transparent; }
li.epic-card.epic-ready { border-left-color:var(--done); }
.epic-head { display:grid; grid-template-columns:16px 1fr 260px 60px; column-gap:14px; row-gap:4px; align-items:center; padding:10px 16px; cursor:pointer; }
.epic-head:hover { background:#fafbfd; }
.chev { color:var(--faint); font-size:0.75rem; transition:transform 0.15s; display:inline-block; }
li.epic-card.open > .epic-head .chev, .feature-block.open > div > .tree-row .chev, li.story-row.open > div > .tree-row .chev { transform:rotate(90deg); }
.epic-title-line { display:flex; align-items:baseline; gap:8px; min-width:0; }
.epic-title-line a { font-weight:700; white-space:nowrap; }
.epic-title { font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.epic-meta { grid-column:2; font-size:0.76rem; color:var(--muted); display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
.epic-meta .sep { color:var(--line); }
.epic-meta .ready { color:var(--done); font-weight:600; }
.epic-progress { grid-column:3; grid-row:1 / span 2; display:flex; flex-direction:column; gap:4px; }
.epic-progress .nums { font-size:0.72rem; color:var(--muted); display:flex; justify-content:space-between; }
.epic-head .pct { grid-column:4; grid-row:1 / span 2; }
.comment-flag { color:var(--muted); }
.comment-flag.none { color:var(--faint); }

.epic-body { display:none; border-top:1px solid var(--line); padding:12px 16px 14px 46px; }
li.epic-card.open .epic-body { display:block; }

/* Acompanhamento (só visível com o épico aberto) */
.tracking { background:#fbfaf6; border:1px solid #efe9da; border-radius:8px; padding:10px 12px; margin-bottom:12px; font-size:0.8rem; }
.tracking-last { color:#444; line-height:1.45; margin-bottom:8px; }
.tracking-label { font-weight:700; color:#8d6e00; margin-right:4px; }
.comment-author { font-weight:700; color:var(--ink); }
.comment-empty { color:var(--faint); font-style:italic; }
.tracking-new { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.tracking-input { flex:1; min-width:220px; padding:6px 10px; border:1px solid var(--line); border-radius:6px; font-size:0.8rem; }
.btn-tracking { padding:6px 12px; font-size:0.78rem; }
.tracking-status { font-size:0.72rem; color:var(--muted); }
.tracking-status.ok { color:var(--done); font-weight:700; }
.tracking-status.err { color:#c62828; font-weight:700; }

/* Árvore Feature > US/Bug > Task em colunas fixas */
.tree-row { display:grid; grid-template-columns:64px minmax(0,1fr) 150px 84px 100px 150px; column-gap:12px; align-items:center; padding:6px 8px; border-radius:6px; font-size:0.82rem; }
.tree-row:hover { background:#f7f8fa; }
.tree-row .id { font-weight:600; font-size:0.78rem; }
.tree-row .title { display:flex; align-items:center; gap:6px; min-width:0; }
.tree-row .title .txt { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tree-row .who { color:var(--muted); font-size:0.76rem; text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tree-row .prog { display:flex; align-items:center; gap:8px; font-size:0.72rem; color:var(--muted); }
.tree-row .prog .bar { flex:1; height:6px; }
.tree-row .chev { width:12px; cursor:pointer; }
.tree-row .chev.blank { visibility:hidden; }
.feature-block > .tree-row { cursor:pointer; font-weight:600; }
.feature-block { border-bottom:1px solid var(--line); padding:2px 0; }
.feature-block:last-child { border-bottom:none; }
.feature-block .story-list, li.story-row .task-list { display:none; list-style:none; }
.feature-block.open .story-list, li.story-row.open .task-list { display:block; }
.story-list .tree-row .title { padding-left:18px; }
.task-list .tree-row .title { padding-left:36px; }
.story-list .tree-row { font-weight:400; }

/* Removidos: apagados e ocultos por padrão */
.removed .txt { text-decoration:line-through; }
.removed { opacity:0.45; }
body:not(.show-removed) .removed { display:none; }


@media (max-width:900px) {
  .kpis { grid-template-columns:1fr 1fr; }
  .kpis .kpi:first-child { grid-column:1 / -1; }
  .epic-head { grid-template-columns:16px 1fr 60px; }
  .epic-progress { grid-column:2; grid-row:auto; }
  .epic-head .pct { grid-column:3; grid-row:1; }
  .tree-row { grid-template-columns:56px minmax(0,1fr) 84px 90px; }
  .tree-row .prog, .tree-row .who { display:none; }
  .epic-body { padding-left:16px; }
}
"""

JS_TEMPLATE = """
// ============================================================
// Configuração específica do dashboard de Releases
// (cliente Azure DevOps vem de ado_common.py)
// ============================================================
const RELEASE_FIELD = __RELEASE_FIELD_JSON__;
const TRACKING_TAG = __TRACKING_TAG_JSON__;
const PRODUTO_OK_TAG = __PRODUTO_OK_TAG_JSON__;
const COMMENTS_CONCURRENCY = 8;
const NO_RELEASE = "Sem release";
const PRIORITY_FIELD = __PRIORITY_FIELD_JSON__;
const DUE_DATE_FIELD = __DUE_DATE_FIELD_JSON__;

// ============================================================
// Comentários de acompanhamento
// ============================================================
async function fetchLastTrackingComment(epicId) {
  const url = `https://dev.azure.com/${ADO_ORG}/${encodeURIComponent(ADO_PROJECT)}/_apis/wit/workItems/${epicId}/comments?api-version=7.1-preview.3&$top=200&order=desc`;
  try {
    const resp = await fetch(url, { headers: adoHeaders() });
    if (!resp.ok) {
      loadWarnings.push(`comentários do épico #${epicId}: HTTP ${resp.status}`);
      return null;
    }
    const data = await resp.json();
    const comments = data.comments || [];
    const matching = comments
      .map(c => ({ text: stripHtml(c.text || ""), author: (c.createdBy || {}).displayName || "", date: (c.createdDate || "").slice(0, 10), full: c.createdDate || "" }))
      .filter(c => c.text.toLowerCase().includes(TRACKING_TAG.toLowerCase()));
    if (!matching.length) return null;
    matching.sort((a, b) => a.full.localeCompare(b.full));
    return matching[matching.length - 1];
  } catch (e) {
    loadWarnings.push(`comentários do épico #${epicId}: ${e.message}`);
    return null;
  }
}

async function saveTrackingComment(epicId) {
  const pat = getPat();
  const input = document.getElementById("commentInput_" + epicId);
  const statusEl = document.getElementById("commentStatus_" + epicId);
  const btn = input.parentElement.querySelector(".btn-tracking");
  const text = input.value.trim();

  if (!pat) { statusEl.textContent = "Configure o PAT acima antes de salvar."; statusEl.className = "tracking-status err"; return; }
  if (!text) { statusEl.textContent = "Digite um comentário antes de salvar."; statusEl.className = "tracking-status err"; return; }

  const fullText = text.includes(TRACKING_TAG) ? text : (text + " " + TRACKING_TAG);

  btn.disabled = true;
  statusEl.textContent = "Salvando...";
  statusEl.className = "tracking-status";

  try {
    const url = `https://dev.azure.com/${ADO_ORG}/${encodeURIComponent(ADO_PROJECT)}/_apis/wit/workItems/${epicId}/comments?api-version=7.1-preview.3`;
    const resp = await fetch(url, { method: "POST", headers: adoHeaders(), body: JSON.stringify({ text: fullText }) });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    const authorName = (data.createdBy && data.createdBy.displayName) || "Você";
    const dateStr = (data.createdDate || "").slice(0, 10);
    document.getElementById("lastComment_" + epicId).innerHTML = `<span class="comment-author">${escapeHtml(authorName)} (${escapeHtml(formatDay(dateStr))}):</span> ${escapeHtml(fullText)}`;
    document.getElementById("commentFlag_" + epicId).innerHTML = commentFlagHtml({ author: authorName, text: fullText, date: dateStr });
    input.value = "";
    statusEl.textContent = "Comentário salvo com sucesso!";
    statusEl.className = "tracking-status ok";
  } catch (err) {
    statusEl.textContent = "Erro ao salvar (verifique o PAT e permissões). " + err.message;
    statusEl.className = "tracking-status err";
  } finally {
    btn.disabled = false;
  }
}
window.saveTrackingComment = saveTrackingComment;

// ============================================================
// Estatísticas
// ============================================================
// Itens em IGNORED_STATES (Removed) aparecem na árvore (ocultos por padrão), mas não entram em contagens/percentuais.
function isCounted(item) { return !IGNORED_STATES.has(item.state); }

const PCT_RULE = "Itens em Closed/Done/Resolved ÷ total de itens (Feature, User Story/Bug e Task com o mesmo peso). Itens Removed não entram.";

function emptyStats() { return { total: 0, done: 0, test: 0, doing: 0, todo: 0, byState: {} }; }
function addToStats(stats, item) {
  if (!isCounted(item)) return;
  stats.total += 1;
  stats[stateGroup(item.state)] += 1;
  stats.byState[item.state] = (stats.byState[item.state] || 0) + 1;
}
function mergeStats(a, b) {
  ["total", "done", "test", "doing", "todo"].forEach(k => { a[k] += b[k]; });
  return a;
}
function pctOf(stats) { return stats.total ? Math.round((stats.done / stats.total) * 100) : 0; }
function pctClass(pct) { return pct >= 80 ? "high" : (pct >= 40 ? "mid" : "low"); }

function epicStats(epic) {
  const s = emptyStats();
  epic.features.forEach(feat => {
    addToStats(s, feat);
    feat.stories.forEach(story => {
      addToStats(s, story);
      story.tasks.forEach(task => addToStats(s, task));
    });
  });
  return s;
}

function featureStats(feature) {
  const s = emptyStats();
  feature.stories.forEach(story => {
    addToStats(s, story);
    story.tasks.forEach(task => addToStats(s, task));
  });
  return s;
}

function progressBar(stats) {
  if (!stats.total) return `<div class="bar" title="sem itens"></div>`;
  const seg = (k, label) => stats[k] ? `<span class="seg-${k}" style="width:${(stats[k] / stats.total) * 100}%" title="${label}: ${stats[k]}"></span>` : "";
  const detail = Object.entries(stats.byState || {}).sort((a, b) => b[1] - a[1]).map(([s, c]) => `${s}: ${c}`).join(" · ");
  return `<div class="bar" title="${escapeHtml(detail)}">${seg("done", "Concluídos")}${seg("test", "Em teste")}${seg("doing", "Em andamento")}${seg("todo", "A fazer")}</div>`;
}

function shortArea(area) {
  const prefix = ADO_PROJECT + String.fromCharCode(92);
  return area.startsWith(prefix) ? area.slice(prefix.length) : area;
}

function formatDay(isoDay) {
  const [y, m, d] = (isoDay || "").split("-");
  return d && m ? `${d}/${m}` : "";
}

function formatFullDay(isoDay) {
  const [y, m, d] = (isoDay || "").split("-");
  return d && m && y ? `${d}/${m}/${y}` : "";
}

// ============================================================
// Prioridade e prazo (Due Date)
// ============================================================
const PRIORITY_LABELS = { 1: "Maior prioridade", 2: "Alta prioridade", 3: "Média prioridade", 4: "Baixa prioridade" };
const DUE_SOON_DAYS = 7;

function parsePriority(value) {
  const n = parseInt(value, 10);
  return PRIORITY_LABELS[n] ? n : null;
}

// Due Date vem como data/hora UTC; converte para a data local (YYYY-MM-DD).
function parseDueDate(value) {
  return value ? localIsoDate(new Date(value)) : null;
}

// Ordem: prioridade (1 → 4, sem prioridade por último), depois prazo mais
// próximo (sem prazo por último), depois ID.
function byPriority(a, b) {
  const pa = a.priority ?? 99, pb = b.priority ?? 99;
  if (pa !== pb) return pa - pb;
  const da = a.dueDate || "9999-12-31", db = b.dueDate || "9999-12-31";
  if (da !== db) return da < db ? -1 : 1;
  return a.id - b.id;
}

function sortTreeByPriority(epics) {
  epics.sort(byPriority);
  epics.forEach(e => {
    e.features.sort(byPriority);
    e.features.forEach(f => {
      f.stories.sort(byPriority);
      f.stories.forEach(s => s.tasks.sort(byPriority));
    });
  });
}

function priorityBadge(priority) {
  if (!priority) return `<span class="prio p-none" title="Sem prioridade">–</span>`;
  return `<span class="prio p${priority}" title="${priority} = ${PRIORITY_LABELS[priority]}">${priority}</span>`;
}

// Prazo acordado: vermelho se vencido (e o item não está concluído),
// laranja se vence nos próximos DUE_SOON_DAYS dias.
function dueDateHtml(item) {
  if (!item.dueDate) return `<span class="due none"></span>`;
  const today = localIsoDate(new Date());
  const soon = localIsoDate(new Date(Date.now() + DUE_SOON_DAYS * 86400000));
  const done = CLOSED_LIKE.has(item.state) || IGNORED_STATES.has(item.state);
  let cls = "", note = "Prazo acordado";
  if (!done && item.dueDate < today) { cls = "late"; note = "Prazo acordado vencido"; }
  else if (!done && item.dueDate <= soon) { cls = "soon"; note = `Prazo acordado vence em até ${DUE_SOON_DAYS} dias`; }
  return `<span class="due ${cls}" title="${note}">${formatFullDay(item.dueDate)}</span>`;
}

// ============================================================
// Render
// ============================================================
function treeRow(item, opts) {
  const chev = opts.expandable ? `<span class="chev">▶</span>` : `<span class="chev blank">▶</span>`;
  return `<div class="tree-row">
    <a class="id" href="${workItemUrl(item.id)}" target="_blank" onclick="event.stopPropagation()">#${item.id}</a>
    <span class="title">${chev}${priorityBadge(item.priority)}${typeMark(item.type)}<span class="txt" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span></span>
    <span class="prog">${opts.prog || ""}</span>
    ${dueDateHtml(item)}
    ${stateLabel(item.state)}
    <span class="who">${escapeHtml(item.assignee)}</span>
  </div>`;
}

function removedClass(item) { return isCounted(item) ? "" : "removed"; }

function renderTask(task) {
  return `<li class="task-row ${removedClass(task)}">${treeRow(task, {})}</li>`;
}

function renderStory(story) {
  const hasTasks = story.tasks.length > 0;
  const tasksHtml = hasTasks ? `<ul class="task-list">${story.tasks.map(renderTask).join("")}</ul>` : "";
  const counted = story.tasks.filter(isCounted);
  const prog = hasTasks ? `${counted.filter(t => CLOSED_LIKE.has(t.state)).length}/${counted.length} tasks` : "";
  const toggle = hasTasks ? ` onclick="this.parentElement.classList.toggle('open')"` : "";
  return `<li class="story-row ${removedClass(story)}">
    <div${toggle} style="${hasTasks ? "cursor:pointer" : ""}">${treeRow(story, { expandable: hasTasks, prog })}</div>
    ${tasksHtml}
  </li>`;
}

function renderFeature(feature) {
  const storiesHtml = feature.stories.length
    ? feature.stories.map(renderStory).join("")
    : '<li class="empty-row">Nenhuma User Story/Bug vinculada.</li>';
  const fs = featureStats(feature);
  const prog = fs.total ? `${progressBar(fs)}<span>${pctOf(fs)}%</span>` : `<span>sem itens</span>`;
  return `<div class="feature-block ${removedClass(feature)}">
    <div onclick="this.parentElement.classList.toggle('open')">${treeRow(feature, { expandable: true, prog })}</div>
    <ul class="story-list">${storiesHtml}</ul>
  </div>`;
}

function renderTracking(epic) {
  const c = epic.lastTrackingComment;
  const lastHtml = c
    ? `<span class="comment-author">${escapeHtml(c.author)} (${escapeHtml(formatDay(c.date))}):</span> ${escapeHtml(c.text)}`
    : `<span class="comment-empty">Nenhum comentário ${escapeHtml(TRACKING_TAG)} ainda.</span>`;
  return `<div class="tracking" onclick="event.stopPropagation()">
    <div class="tracking-last"><span class="tracking-label">Último ${escapeHtml(TRACKING_TAG)}:</span> <span id="lastComment_${epic.id}">${lastHtml}</span></div>
    <div class="tracking-new">
      <input type="text" class="tracking-input" id="commentInput_${epic.id}" placeholder="Novo comentário de acompanhamento...">
      <button class="btn btn-tracking" onclick="saveTrackingComment(${epic.id})">Salvar no Azure</button>
      <span class="tracking-status" id="commentStatus_${epic.id}"></span>
    </div>
  </div>`;
}

function commentFlagHtml(c) {
  return c
    ? `<span class="comment-flag" title="${escapeHtml(c.author + ": " + c.text)}">💬 ${escapeHtml(formatDay(c.date))}</span>`
    : `<span class="comment-flag none" title="Nenhum comentário ${escapeHtml(TRACKING_TAG)}">💬 –</span>`;
}

function renderEpic(epic) {
  const stats = epicStats(epic);
  const pct = pctOf(stats);
  const featuresHtml = epic.features.length
    ? epic.features.map(renderFeature).join("")
    : '<p class="empty-row">Nenhuma Feature vinculada a este épico.</p>';

  const searchTerms = [String(epic.id), epic.title, epic.assignee, epic.area];
  epic.features.forEach(feat => {
    searchTerms.push(String(feat.id), feat.title, feat.assignee);
    feat.stories.forEach(story => {
      searchTerms.push(String(story.id), story.title, story.assignee);
      story.tasks.forEach(task => searchTerms.push(String(task.id), task.title, task.assignee));
    });
  });

  const li = document.createElement("li");
  li.className = "epic-card" + (epic.readyForDev ? " epic-ready" : "");
  li.dataset.search = searchTerms.join(" ").toLowerCase();
  li.dataset.area = epic.area;
  li.dataset.release = epic.release;
  li.dataset.features = epic.features.filter(isCounted).length;
  li.dataset.stories = epic.features.reduce((a, f) => a + f.stories.filter(isCounted).length, 0);
  li.dataset.tasks = epic.features.reduce((a, f) => a + f.stories.reduce((a2, s) => a2 + s.tasks.filter(isCounted).length, 0), 0);
  ["total", "done", "test", "doing", "todo"].forEach(k => { li.dataset[k] = stats[k]; });
  li.dataset.ready = epic.readyForDev ? "1" : "0";

  li.innerHTML = `
    <div class="epic-head" onclick="this.parentElement.classList.toggle('open')">
      <span class="chev">▶</span>
      <div class="epic-title-line">
        ${priorityBadge(epic.priority)}
        <a href="${workItemUrl(epic.id)}" target="_blank" onclick="event.stopPropagation()">#${epic.id}</a>
        <span class="epic-title" title="${escapeHtml(epic.title)}">${escapeHtml(epic.title)}</span>
      </div>
      <div class="epic-progress">
        ${progressBar(stats)}
        <div class="nums"><span>${stats.done}/${stats.total} concluídos</span><span>${escapeHtml(epic.assignee)}</span></div>
      </div>
      <span class="pct ${pctClass(pct)}" title="${PCT_RULE}">${stats.total ? pct + "%" : "–"}</span>
      <div class="epic-meta">
        <span>${escapeHtml(shortArea(epic.area))}</span><span class="sep">|</span>
        <span>${escapeHtml(epic.state)}</span><span class="sep">|</span>
        <span id="commentFlag_${epic.id}">${commentFlagHtml(epic.lastTrackingComment)}</span>
        ${epic.dueDate ? `<span class="sep">|</span><span>prazo ${dueDateHtml(epic)}</span>` : ""}
        ${epic.readyForDev ? `<span class="sep">|</span><span class="ready" title="Tag ${escapeHtml(PRODUTO_OK_TAG)}">✓ pronto p/ dev</span>` : ""}
      </div>
    </div>
    <div class="epic-body">
      ${renderTracking(epic)}
      ${featuresHtml}
    </div>
  `;
  return li;
}

// Ordem das releases: natural ("2026 R9" antes de "2026 R10"), "Sem release" por último.
function compareReleases(a, b) {
  return (a === NO_RELEASE) - (b === NO_RELEASE) || a.localeCompare(b, "pt-BR", { numeric: true });
}

// Agrupa os épicos por release (todas as releases encontradas + "Sem release").
function renderReleaseGroups(epics) {
  const byRelease = {};
  epics.forEach(e => (byRelease[e.release] = byRelease[e.release] || []).push(e));
  const releases = Object.keys(byRelease).sort(compareReleases);
  const container = document.getElementById("epicList");
  container.innerHTML = "";
  releases.forEach(rel => {
    const section = document.createElement("section");
    section.className = "release-group";
    section.dataset.release = rel;
    section.innerHTML = `<div class="release-head">
        <h2>${escapeHtml(rel)}</h2>
        <span class="count"></span>
        <span class="bar-slot"></span>
        <span class="pct"></span>
      </div>
      <ul class="epic-list"></ul>`;
    const ul = section.querySelector("ul");
    byRelease[rel].forEach(e => ul.appendChild(renderEpic(e)));
    container.appendChild(section);
  });
}

// ============================================================
// Filtros / KPIs
// ============================================================
function statsFromLis(lis) {
  const s = emptyStats();
  lis.forEach(li => ["total", "done", "test", "doing", "todo"].forEach(k => { s[k] += parseInt(li.dataset[k] || "0", 10); }));
  return s;
}

function updateKpis(visibleLis) {
  const sum = key => visibleLis.reduce((a, li) => a + parseInt(li.dataset[key] || "0", 10), 0);
  const stats = statsFromLis(visibleLis);
  document.getElementById("kpiEpics").textContent = visibleLis.length;
  document.getElementById("kpiFeatures").textContent = sum("features");
  document.getElementById("kpiStories").textContent = sum("stories");
  document.getElementById("kpiTasks").textContent = sum("tasks");
  document.getElementById("kpiReady").textContent = visibleLis.filter(li => li.dataset.ready === "1").length;
  document.getElementById("kpiPct").textContent = stats.total ? ((stats.done / stats.total) * 100).toFixed(1) + "%" : "–";
}

function applyFilter() {
  const term = document.getElementById("searchBox").value.trim().toLowerCase();
  const area = document.getElementById("areaSelect").value;
  const release = document.getElementById("releaseSelect").value;
  const readyOnly = document.getElementById("readyOnly").checked;
  const visible = [];
  document.querySelectorAll("#epicList section.release-group").forEach(section => {
    const groupVisible = [];
    section.querySelectorAll("li.epic-card").forEach(li => {
      const match = (!term || (li.dataset.search || "").includes(term))
        && (!area || li.dataset.area === area)
        && (!release || li.dataset.release === release)
        && (!readyOnly || li.dataset.ready === "1");
      li.style.display = match ? "" : "none";
      if (match && term) li.classList.add("open");
      if (match) groupVisible.push(li);
    });
    section.style.display = groupVisible.length ? "" : "none";
    const gs = statsFromLis(groupVisible);
    const gp = pctOf(gs);
    section.querySelector(".count").textContent = `${groupVisible.length} épico(s) · ${gs.done}/${gs.total} itens concluídos`;
    section.querySelector(".bar-slot").outerHTML = `<span class="bar-slot" style="flex:0 0 160px;margin-left:auto">${progressBar(gs)}</span>`;
    const pctEl = section.querySelector(".release-head .pct");
    pctEl.textContent = gs.total ? gp + "%" : "–";
    pctEl.className = "pct " + pctClass(gp);
    visible.push(...groupVisible);
  });
  updateKpis(visible);
}
document.getElementById("searchBox").addEventListener("input", applyFilter);
document.getElementById("areaSelect").addEventListener("change", applyFilter);
document.getElementById("releaseSelect").addEventListener("change", applyFilter);
document.getElementById("readyOnly").addEventListener("change", applyFilter);
document.getElementById("showRemoved").addEventListener("change", (e) => {
  document.body.classList.toggle("show-removed", e.target.checked);
});

let allExpanded = false;
document.getElementById("btnToggleAll").addEventListener("click", (e) => {
  allExpanded = !allExpanded;
  document.querySelectorAll("li.epic-card, .feature-block").forEach(el => el.classList.toggle("open", allExpanded));
  e.target.textContent = allExpanded ? "Recolher tudo" : "Expandir tudo";
});

// ============================================================
// Atualizar dados (busca real no Azure DevOps)
// ============================================================
function populateSelectOptions(selectId, values, allLabel, labelFn) {
  const select = document.getElementById(selectId);
  const label = labelFn || (v => v);
  select.innerHTML = `<option value="">${allLabel}</option>` + values.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(label(v))}</option>`).join("");
}

// Campos comuns de um work item da árvore.
function toItem(f) {
  return {
    id: f["System.Id"], title: f["System.Title"] || "", type: f["System.WorkItemType"] || "",
    state: f["System.State"] || "", assignee: extractName(f["System.AssignedTo"]), parent: f["System.Parent"],
    priority: parsePriority(f[PRIORITY_FIELD]), dueDate: parseDueDate(f[DUE_DATE_FIELD]),
  };
}

async function refreshData() {
  setStatus("Carregando épicos do Azure DevOps...", "");

  try {
    // 1) Épicos com qualquer release preenchida (todas as áreas).
    const query = `SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '${wiqlStr(ADO_PROJECT)}' AND [System.WorkItemType] = 'Epic' AND [${RELEASE_FIELD}] <> '' ORDER BY [System.Title]`;
    // 2) Épicos sem release: só os da área do time e ainda não encerrados,
    //    para não trazer o projeto inteiro nem o histórico antigo.
    const queryNoRelease = `SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '${wiqlStr(ADO_PROJECT)}' AND [System.WorkItemType] = 'Epic' AND [${RELEASE_FIELD}] = '' AND [System.AreaPath] UNDER '${wiqlStr(AREA_PATH)}' AND [System.State] NOT IN ('Closed', 'Done', 'Removed') ORDER BY [System.Title]`;
    const [withRelease, withoutRelease] = await Promise.all([
      wiql(query, "épicos com release"),
      wiql(queryNoRelease, "épicos sem release"),
    ]);
    const epicIds = [...new Set([...withRelease, ...withoutRelease])];
    const basicFields = ["System.Id", "System.Title", "System.WorkItemType", "System.State", "System.AssignedTo", "System.AreaPath", "System.Parent", PRIORITY_FIELD, DUE_DATE_FIELD];
    const releaseFields = basicFields.concat([RELEASE_FIELD, "System.Tags"]);
    const epicsRaw = epicIds.length ? await getWorkItemsBatch(epicIds, releaseFields) : [];
    setStatus(`${epicsRaw.length} épicos encontrados. Buscando features...`, "");

    const epicsById = {};
    epicsRaw.forEach(wi => {
      const f = wi.fields;
      const tagsRaw = f["System.Tags"] || "";
      const readyForDev = tagsRaw.split(";").map(t => t.trim()).some(t => t.toLowerCase() === PRODUTO_OK_TAG.toLowerCase());
      epicsById[f["System.Id"]] = Object.assign(toItem(f), {
        area: f["System.AreaPath"] || "", release: String(f[RELEASE_FIELD] || "").trim() || NO_RELEASE,
        readyForDev: readyForDev, features: [],
      });
    });

    const featureIds = await queryChildrenOfMany(Object.keys(epicsById), ["Feature"]);
    const featuresRaw = featureIds.length ? await getWorkItemsBatch(featureIds, basicFields) : [];
    setStatus(`${featuresRaw.length} features encontradas. Buscando user stories/bugs...`, "");

    const featuresById = {};
    featuresRaw.forEach(wi => {
      const f = wi.fields;
      const item = Object.assign(toItem(f), { stories: [] });
      featuresById[item.id] = item;
      if (epicsById[item.parent]) epicsById[item.parent].features.push(item);
    });

    const storyIds = await queryChildrenOfMany(Object.keys(featuresById), ["User Story", "Bug"]);
    const storiesRaw = storyIds.length ? await getWorkItemsBatch(storyIds, basicFields) : [];
    setStatus(`${storiesRaw.length} user stories/bugs encontradas. Buscando tasks...`, "");

    const storiesById = {};
    storiesRaw.forEach(wi => {
      const f = wi.fields;
      const item = Object.assign(toItem(f), { tasks: [] });
      storiesById[item.id] = item;
      if (featuresById[item.parent]) featuresById[item.parent].stories.push(item);
    });

    const taskIds = await queryChildrenOfMany(Object.keys(storiesById), ["Task"]);
    const tasksRaw = taskIds.length ? await getWorkItemsBatch(taskIds, basicFields) : [];

    tasksRaw.forEach(wi => {
      const f = wi.fields;
      const item = toItem(f);
      if (storiesById[item.parent]) storiesById[item.parent].tasks.push(item);
    });

    const epics = Object.values(epicsById);
    sortTreeByPriority(epics);

    setStatus(`Buscando últimos comentários #acompanhamento de ${epics.length} épicos...`, "");
    let commentsDone = 0;
    await runWithConcurrency(epics, COMMENTS_CONCURRENCY, async e => {
      e.lastTrackingComment = await fetchLastTrackingComment(e.id);
      commentsDone++;
      if (commentsDone % 5 === 0 || commentsDone === epics.length) {
        setStatus(`Buscando comentários #acompanhamento: ${commentsDone}/${epics.length} épicos...`, "");
      }
    });

    // Render
    if (!epics.length) {
      document.getElementById("epicList").innerHTML = '<p class="empty-row">Nenhum épico encontrado.</p>';
    } else {
      renderReleaseGroups(epics);
    }

    const areas = [...new Set(epics.map(e => e.area).filter(Boolean))].sort();
    const releases = [...new Set(epics.map(e => e.release).filter(Boolean))].sort(compareReleases);
    populateSelectOptions("areaSelect", areas, "Todas as áreas", shortArea);
    populateSelectOptions("releaseSelect", releases, "Todas as releases");

    applyFilter();
    finishStatus(`Atualizado: ${epics.length} épicos carregados às ${new Date().toLocaleTimeString('pt-BR')}.`);
  } catch (err) {
    document.getElementById("epicList").innerHTML = `<p class="empty-row">Falha ao carregar dados: ${escapeHtml(err.message)}</p>`;
    throw err;
  }
}

initDashboard(refreshData);
"""

TOOLBAR_HTML = """<input type="text" id="searchBox" placeholder="Filtrar por ID, título ou responsável...">
    <select id="releaseSelect"><option value="">Todas as releases</option></select>
    <select id="areaSelect"><option value="">Todas as áreas</option></select>
    <label class="check"><input type="checkbox" id="readyOnly"> Só prontos p/ dev</label>
    <label class="check"><input type="checkbox" id="showRemoved"> Mostrar removidos</label>
    <span class="spacer"></span>
    <button class="btn" id="btnToggleAll">Expandir tudo</button>
"""

BODY_HTML = """  <div class="kpis">
    <div class="kpi">
      <div class="kpi-counts">
        <div><b id="kpiEpics">-</b><span>épicos</span></div>
        <div><b id="kpiFeatures">-</b><span>features</span></div>
        <div><b id="kpiStories">-</b><span>user stories / bugs</span></div>
        <div><b id="kpiTasks">-</b><span>tasks</span></div>
      </div>
    </div>
    <div class="kpi"><div class="n" id="kpiPct">-</div><div class="l" title="Itens em Closed/Done/Resolved ÷ total de itens (Feature, User Story/Bug e Task com o mesmo peso). Itens Removed não entram.">concluído (geral) ⓘ</div></div>
    <div class="kpi ready"><div class="n" id="kpiReady">-</div><div class="l">prontos p/ dev</div></div>
  </div>

  <div class="legend">
    <span><i class="seg-done"></i>Concluídos (Closed/Done/Resolved)</span>
    <span><i class="seg-test"></i>Em teste</span>
    <span><i class="seg-doing"></i>Em andamento</span>
    <span><i class="seg-todo"></i>A fazer (New/Ready)</span>
  </div>
  <div class="legend">
    <span>Prioridade:</span>
    <span><span class="prio p1">1</span> Maior</span>
    <span><span class="prio p2">2</span> Alta</span>
    <span><span class="prio p3">3</span> Média</span>
    <span><span class="prio p4">4</span> Baixa</span>
    <span class="sep-legend">·</span>
    <span>Prazo acordado (Due Date): <span class="due late">vencido</span> · <span class="due soon">vence em até 7 dias</span></span>
  </div>

  <div id="epicList">
    <p class="empty-row">Configure o PAT (⚙) e clique em "Atualizar dados" para carregar os épicos.</p>
  </div>
"""


def generate_html():
    js = (
        JS_TEMPLATE
        .replace("__RELEASE_FIELD_JSON__", json.dumps(RELEASE_FIELD))
        .replace("__TRACKING_TAG_JSON__", json.dumps(TRACKING_TAG))
        .replace("__PRODUTO_OK_TAG_JSON__", json.dumps(PRODUTO_OK_TAG))
        .replace("__PRIORITY_FIELD_JSON__", json.dumps(PRIORITY_FIELD))
        .replace("__DUE_DATE_FIELD_JSON__", json.dumps(DUE_DATE_FIELD))
    )
    return render_page(
        title="Releases - Épicos, Features e User Stories",
        heading="Releases",
        subtitle="Épicos por release · dados ao vivo do Azure DevOps",
        subtitle_title=("Épicos de todas as releases (campo Custom.SR_RELEASE preenchido, qualquer área) "
                        "e, em \"Sem release\", os épicos da área Folha X ainda não encerrados e sem release informada. "
                        "Inclui Features, User Stories/Bugs e Tasks."),
        toolbar=TOOLBAR_HTML,
        body=BODY_HTML,
        css=CSS,
        js=js,
        pat_scope="Work Items (Read &amp; Write)",
    )


def main():
    write_html(OUTPUT_FILE, generate_html(), "Dashboard Releases")


if __name__ == "__main__":
    main()
