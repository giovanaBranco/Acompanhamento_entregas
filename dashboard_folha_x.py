"""
Dashboard Folha X - Acompanhamento de Desenvolvimento - DINÂMICO
=================================================================
Indicadores do time Folha X no Azure DevOps (itens em aberto, ou seja,
fora de Closed/Removed/Done, na área do time):
- Contagens de épicos, features e work items (Bug, User Story e Task) em
  aberto e quantidade de desenvolvedores.
- Resumo por status dos work items (cada card abre a consulta no Azure DevOps).
- Demandas por desenvolvedor: total, por tipo e por estado (as mesmas
  colunas de estado dos cards de status). Desenvolvedor sem nada em Ready
  nem em Active fica destacado. Itens sem responsável aparecem na linha
  "Não atribuído", ao final da tabela.
- Épicos -> Features: lista recolhível com todos os épicos em aberto
  carregados (qualquer estado: New, Ready, Active...), suas features em
  aberto e a quantidade de work items em aberto de cada feature. Features
  cujo épico pai não foi carregado (encerrado ou de outra área) aparecem
  agrupadas pelo ID do pai; features sem pai ficam em "Sem épico".

Os dados são buscados diretamente do Azure DevOps PELO NAVEGADOR,
usando um PAT salvo no localStorage. Não é necessário rodar este
script sempre que os dados mudarem — basta abrir o HTML e clicar em
"Atualizar dados".

Uso:
    python dashboard_folha_x.py
"""

import json

from ado_common import render_page, write_html

OUTPUT_FILE = "dashboard_folha_x.html"

# Ordem das colunas/cards de estado; estados fora desta lista vão ao final.
STATUS_ORDER = ["New", "Ready", "Active", "Review", "Test", "Resolved"]

CSS = """
.kpis.main { grid-template-columns:2fr 1fr 1fr; }
.kpis.status { grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); }
.kpis.status .kpi { padding:10px 14px; }
.kpis.status .n { font-size:1.3rem; color:var(--ink); }
.kpis.status .l .state { font-size:0.75rem; }

.dev-table td.zero { color:var(--faint); }
.dev-table tr.unassigned td { color:var(--muted); font-style:italic; }
.dev-table td.dev { font-weight:600; }

.epic-title { font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; flex:1; }
.collapsible > .head a.id { font-weight:700; white-space:nowrap; }
.collapsible > .head .state { min-width:70px; }
.collapsible > .head .meta { font-size:0.76rem; color:var(--muted); white-space:nowrap; min-width:130px; text-align:right; }
.collapsible > .head .bar { flex:0 0 140px; }
.collapsible > .head .bar.empty { visibility:hidden; }
.feat-table td:first-child { width:80px; }
.feat-table td.title { max-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.feat-table col.c-state { width:120px; } .feat-table col.c-who { width:180px; } .feat-table col.c-n { width:90px; }

@media (max-width:900px) {
  .kpis.main { grid-template-columns:1fr 1fr; }
  .kpis.main .kpi:first-child { grid-column:1 / -1; }
  .collapsible > .head .bar { display:none; }
}
"""

JS_TEMPLATE = """
// ============================================================
// Dashboard de acompanhamento do time
// (cliente Azure DevOps vem de ado_common.py)
// ============================================================
const STATUS_ORDER = __STATUS_ORDER_JSON__;
const WI_TYPES = ["Bug", "User Story", "Task"];
const OPEN_CLAUSE = "AND [System.State] <> 'Closed' AND [System.State] <> 'Removed' AND [System.State] <> 'Done'";
const UNASSIGNED = "Não atribuído";

function baseWhere() {
  return `[System.TeamProject] = '${wiqlStr(ADO_PROJECT)}' AND [System.AreaPath] UNDER '${wiqlStr(AREA_PATH)}'`;
}
function wiTypesClause() { return `[System.WorkItemType] IN (${WI_TYPES.map(t => `'${t}'`).join(", ")})`; }
const WI_SELECT = "SELECT [System.Id], [System.Title], [System.WorkItemType], [System.AssignedTo], [System.State] FROM WorkItems";

// Estados exibidos: os de STATUS_ORDER presentes (Ready e Active sempre, por
// causa do destaque) e depois qualquer outro estado encontrado.
function stateColumns(allStates) {
  const cols = STATUS_ORDER.filter(s => allStates[s] || s === "Ready" || s === "Active");
  Object.keys(allStates).sort().forEach(s => { if (!cols.includes(s)) cols.push(s); });
  return cols;
}

// Barra com a distribuição dos work items em aberto por grupo de estado.
function wiBar(items) {
  const counts = { done: 0, test: 0, doing: 0, todo: 0 };
  items.forEach(i => { const g = stateGroup(i.state); if (g in counts) counts[g]++; });
  const total = items.length;
  if (!total) return `<div class="bar empty"></div>`;
  const labels = { done: "Resolvidos", test: "Em teste/review", doing: "Em andamento", todo: "A fazer" };
  const segs = ["done", "test", "doing", "todo"].map(k => counts[k]
    ? `<span class="seg-${k}" style="width:${(counts[k] / total) * 100}%"></span>` : "").join("");
  const tip = ["done", "test", "doing", "todo"].filter(k => counts[k]).map(k => `${labels[k]}: ${counts[k]}`).join(" · ");
  return `<div class="bar" title="${escapeHtml(tip)}">${segs}</div>`;
}

function cell(n, cls) { return `<td class="num ${n ? "" : "zero"} ${cls || ""}">${n}</td>`; }

// ============================================================
// Render
// ============================================================
function renderKpis(data) {
  document.getElementById("kpiEpics").textContent = data.totals.epics;
  document.getElementById("kpiFeatures").textContent = data.totals.features;
  document.getElementById("kpiWis").textContent = data.totals.workItems;
  document.getElementById("kpiDevs").textContent = data.nDevs;
  document.getElementById("kpiIdle").textContent = data.idleDevs;
  document.getElementById("kpiIdleCard").classList.toggle("warn", data.idleDevs > 0);
  document.getElementById("kpiIdleCard").classList.toggle("good", data.idleDevs === 0);
  document.getElementById("kpiUnassigned").textContent = data.unassigned;
  document.getElementById("kpiUnassignedCard").classList.toggle("warn", data.unassigned > 0);

  document.getElementById("statusKpis").innerHTML = data.stateCols.filter(s => data.allStates[s]).map(state => {
    const q = `${WI_SELECT} WHERE ${baseWhere()} AND ${wiTypesClause()} AND [System.State] = '${wiqlStr(state)}'`;
    return `<a class="kpi" href="${queryUrl(q)}" target="_blank" title="Abrir consulta no Azure DevOps">
      <div class="n">${data.allStates[state]}</div><div class="l">${stateLabel(state)}</div></a>`;
  }).join("");
}

function renderDevTable(data) {
  const cols = data.stateCols;
  const head = `<tr><th>Desenvolvedor</th><th class="num">Total</th><th class="num">Bugs</th><th class="num">User Stories</th><th class="num">Tasks</th>`
    + cols.map(s => `<th class="num">${stateLabel(s)}</th>`).join("") + `</tr>`;

  const devRow = (dev, items) => {
    const isUnassigned = dev === UNASSIGNED;
    const byType = t => items.filter(i => i.type === t).length;
    const byState = s => items.filter(i => i.state === s).length;
    const ready = byState("Ready"), active = byState("Active");
    // Destaque: sem nada em Ready nem Active (alerta) ou só sem Ready (atenção).
    const idle = !isUnassigned && !ready && !active;
    const readyCls = isUnassigned ? "" : (idle ? "cell-alert" : (!ready ? "cell-warn" : ""));
    const assignedClause = isUnassigned ? "[System.AssignedTo] = ''" : `[System.AssignedTo] = '${wiqlStr(dev)}'`;
    const q = `${WI_SELECT} WHERE ${baseWhere()} AND ${wiTypesClause()} ${OPEN_CLAUSE} AND ${assignedClause}`;
    const title = idle ? ' title="Sem itens em Ready nem em Active"' : "";
    return `<tr class="${isUnassigned ? "unassigned" : ""}">
      <td class="dev ${idle ? "cell-alert" : ""}"${title}><a href="${queryUrl(q)}" target="_blank" style="color:inherit">${escapeHtml(dev)}</a></td>
      ${cell(items.length)}${cell(byType("Bug"))}${cell(byType("User Story"))}${cell(byType("Task"))}
      ${cols.map(s => cell(byState(s), s === "Ready" ? readyCls : (s === "Active" && idle ? "cell-alert" : ""))).join("")}
    </tr>`;
  };

  const devs = Object.entries(data.devItems).filter(([d]) => d !== UNASSIGNED)
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0], "pt-BR"));
  let rows = devs.map(([d, items]) => devRow(d, items)).join("");
  if (data.devItems[UNASSIGNED]) rows += devRow(UNASSIGNED, data.devItems[UNASSIGNED]);
  if (!rows) rows = `<tr><td colspan="${5 + cols.length}" class="empty-row">Nenhum work item em aberto.</td></tr>`;

  return `<div class="card">
    <h3>Demandas por desenvolvedor</h3>
    <div class="tbl-wrap"><table class="dev-table"><thead>${head}</thead><tbody>${rows}</tbody></table></div>
    <p class="note">Em vermelho: desenvolvedor sem nada em Ready nem em Active. Em amarelo: sem nada em Ready. Clique no nome para abrir os itens no Azure DevOps.</p>
  </div>`;
}

function renderEpicGroup(group, data) {
  const wis = group.features.flatMap(f => data.featureChildren[f.id] || []);
  const featureRows = group.features.map(feat => {
    const children = data.featureChildren[feat.id] || [];
    const q = `${WI_SELECT} WHERE ${baseWhere()} AND ${wiTypesClause()} AND [System.Parent] = ${feat.id}`;
    const childrenCell = children.length ? `<a href="${queryUrl(q)}" target="_blank">${children.length}</a>` : "0";
    return `<tr>
      <td><a href="${workItemUrl(feat.id)}" target="_blank">#${feat.id}</a></td>
      <td class="title" title="${escapeHtml(feat.title)}">${escapeHtml(feat.title)}</td>
      <td>${stateLabel(feat.state)}</td>
      <td>${escapeHtml(feat.assignedTo)}</td>
      <td class="num">${childrenCell}</td>
    </tr>`;
  }).join("");
  const body = group.features.length
    ? `<div class="tbl-wrap"><table class="feat-table">
        <colgroup><col><col><col class="c-state"><col class="c-who"><col class="c-n"></colgroup>
        <thead><tr><th>ID</th><th>Feature</th><th>Estado</th><th>Responsável</th><th class="num">WIs em aberto</th></tr></thead>
        <tbody>${featureRows}</tbody></table></div>`
    : `<p class="empty-row">Nenhuma feature em aberto neste épico.</p>`;

  const idHtml = group.epicId
    ? `<a class="id" href="${workItemUrl(group.epicId)}" target="_blank" onclick="event.stopPropagation()">#${group.epicId}</a>` : "";
  const search = [group.epicId || "", group.epicName, ...group.features.flatMap(f => [f.id, f.title, f.assignedTo])].join(" ").toLowerCase();
  return `<div class="collapsible epic" data-search="${escapeHtml(search)}">
    <div class="head" onclick="this.parentElement.classList.toggle('open')">
      <span class="chev">▶</span>
      ${idHtml}
      <span class="epic-title" title="${escapeHtml(group.epicName)}">${escapeHtml(group.epicName)}</span>
      ${group.epicState ? stateLabel(group.epicState) : ""}
      <span class="meta">${group.features.length} feature(s) · ${wis.length} WI(s)</span>
      ${wiBar(wis)}
    </div>
    <div class="body">${body}</div>
  </div>`;
}

function renderDashboard(data) {
  renderKpis(data);
  const epicsHtml = data.epicGroups.length
    ? data.epicGroups.map(g => renderEpicGroup(g, data)).join("")
    : `<p class="empty-row">Nenhum épico ou feature em aberto.</p>`;
  document.getElementById("content").innerHTML = `
    ${renderDevTable(data)}
    <div class="section-title">Épicos e features <span class="count">${data.epicGroups.length} grupo(s)</span></div>
    <div class="legend">
      <span>Barra: work items em aberto por estado</span>
      <span><i class="seg-done"></i>Resolvidos</span>
      <span><i class="seg-test"></i>Em teste/review</span>
      <span><i class="seg-doing"></i>Em andamento</span>
      <span><i class="seg-todo"></i>A fazer (New/Ready)</span>
    </div>
    <div id="epicList">${epicsHtml}</div>`;
  applyFilter();
  document.getElementById("footerNote").textContent = `Dados do Azure DevOps · atualizado em ${new Date().toLocaleString("pt-BR")}`;
}

// ============================================================
// Filtro e expandir/recolher
// ============================================================
function applyFilter() {
  const term = document.getElementById("searchBox").value.trim().toLowerCase();
  document.querySelectorAll("#epicList .collapsible").forEach(el => {
    const match = !term || el.dataset.search.includes(term);
    el.style.display = match ? "" : "none";
  });
}
document.getElementById("searchBox").addEventListener("input", applyFilter);

let allExpanded = false;
document.getElementById("btnToggleAll").addEventListener("click", (e) => {
  allExpanded = !allExpanded;
  document.querySelectorAll("#epicList .collapsible").forEach(el => el.classList.toggle("open", allExpanded));
  e.target.textContent = allExpanded ? "Recolher tudo" : "Expandir tudo";
});

// ============================================================
// Atualizar dados (busca real no Azure DevOps)
// ============================================================
async function refreshData() {
  setStatus("Carregando dados do Azure DevOps...", "");
  try {
    const queryEpics = `SELECT [System.Id] FROM WorkItems WHERE ${baseWhere()} AND [System.WorkItemType] = 'Epic' ${OPEN_CLAUSE} ORDER BY [System.Title]`;
    const epicIds = await wiql(queryEpics, "épicos em aberto");
    const epicsRaw = epicIds.length ? await getWorkItemsBatch(epicIds, ["System.Id", "System.Title", "System.State"]) : [];

    const queryFeatures = `SELECT [System.Id] FROM WorkItems WHERE ${baseWhere()} AND [System.WorkItemType] = 'Feature' ${OPEN_CLAUSE} ORDER BY [System.Title]`;
    const featureIds = await wiql(queryFeatures, "features em aberto");
    const featuresRaw = featureIds.length ? await getWorkItemsBatch(featureIds, ["System.Id", "System.Title", "System.State", "System.Parent", "System.AssignedTo"]) : [];

    const queryWi = `SELECT [System.Id] FROM WorkItems WHERE ${baseWhere()} AND ${wiTypesClause()} ${OPEN_CLAUSE} ORDER BY [System.AssignedTo]`;
    const wiIds = await wiql(queryWi, "work items em aberto");
    const wiRaw = wiIds.length ? await getWorkItemsBatch(wiIds, ["System.Id", "System.Title", "System.State", "System.WorkItemType", "System.AssignedTo", "System.Parent"]) : [];

    setStatus(`${epicsRaw.length} épicos, ${featuresRaw.length} features, ${wiRaw.length} work items. Processando...`, "");

    // Grupos: todos os épicos em aberto carregados (qualquer estado), mesmo sem features.
    const groups = {};
    epicsRaw.forEach(e => {
      const id = e.fields["System.Id"];
      groups[id] = { epicId: id, epicName: e.fields["System.Title"] || "Sem título", epicState: e.fields["System.State"] || "", features: [] };
    });

    const featureMap = {};
    featuresRaw.forEach(f => {
      const feat = {
        id: f.fields["System.Id"],
        title: f.fields["System.Title"] || "Sem título",
        state: f.fields["System.State"] || "",
        parent: f.fields["System.Parent"],
        assignedTo: extractName(f.fields["System.AssignedTo"]),
      };
      featureMap[feat.id] = feat;
      const key = feat.parent || "none";
      if (!groups[key]) {
        // Pai não carregado: épico encerrado ou de outra área (ou feature sem épico).
        groups[key] = feat.parent
          ? { epicId: feat.parent, epicName: `Épico #${feat.parent} (encerrado ou fora da área)`, epicState: "", features: [] }
          : { epicId: null, epicName: "Sem épico", epicState: "", features: [] };
      }
      groups[key].features.push(feat);
    });

    const devItems = {}, featureChildren = {}, allStates = {};
    wiRaw.forEach(wi => {
      const f = wi.fields;
      const item = { id: f["System.Id"], type: f["System.WorkItemType"] || "", state: f["System.State"] || "Outro", parent: f["System.Parent"] };
      const dev = extractName(f["System.AssignedTo"]);
      (devItems[dev] = devItems[dev] || []).push(item);
      if (item.parent && featureMap[item.parent]) (featureChildren[item.parent] = featureChildren[item.parent] || []).push(item);
      allStates[item.state] = (allStates[item.state] || 0) + 1;
    });

    const devNames = Object.keys(devItems).filter(d => d !== UNASSIGNED);
    const idleDevs = devNames.filter(d => !devItems[d].some(i => i.state === "Ready" || i.state === "Active")).length;

    renderDashboard({
      devItems, featureChildren, allStates,
      stateCols: stateColumns(allStates),
      epicGroups: Object.values(groups).sort((a, b) =>
        b.features.length - a.features.length || (a.epicId === null) - (b.epicId === null) || a.epicName.localeCompare(b.epicName, "pt-BR")),
      nDevs: devNames.length,
      idleDevs,
      unassigned: (devItems[UNASSIGNED] || []).length,
      totals: { epics: epicsRaw.length, features: featuresRaw.length, workItems: wiRaw.length },
    });
    finishStatus(`Atualizado: ${epicsRaw.length} épicos, ${featuresRaw.length} features e ${wiRaw.length} work items às ${new Date().toLocaleTimeString("pt-BR")}.`);
  } catch (err) {
    document.getElementById("content").innerHTML = `<div class="empty-state">Falha ao carregar dados: ${escapeHtml(err.message)}</div>`;
    throw err;
  }
}

initDashboard(refreshData);
"""

TOOLBAR_HTML = """<input type="text" id="searchBox" placeholder="Filtrar épicos e features por ID, título ou responsável...">
    <span class="spacer"></span>
    <button class="btn" id="btnToggleAll">Expandir tudo</button>
"""

BODY_HTML = """  <div class="kpis main">
    <div class="kpi">
      <div class="kpi-counts">
        <div><b id="kpiEpics">-</b><span>épicos em aberto</span></div>
        <div><b id="kpiFeatures">-</b><span>features em aberto</span></div>
        <div><b id="kpiWis">-</b><span>work items em aberto</span></div>
        <div><b id="kpiDevs">-</b><span>desenvolvedores</span></div>
      </div>
    </div>
    <div class="kpi" id="kpiIdleCard"><div class="n" id="kpiIdle">-</div><div class="l" title="Desenvolvedores sem nenhum item em Ready nem em Active">devs sem Ready/Active</div></div>
    <div class="kpi" id="kpiUnassignedCard"><div class="n" id="kpiUnassigned">-</div><div class="l">work items não atribuídos</div></div>
  </div>
  <div class="kpis status" id="statusKpis"></div>

  <div id="content">
    <div class="empty-state">Configure o PAT (⚙) e clique em "Atualizar dados" para carregar o dashboard.</div>
  </div>

  <div class="footer" id="footerNote"></div>
"""


def generate_html():
    js = JS_TEMPLATE.replace("__STATUS_ORDER_JSON__", json.dumps(STATUS_ORDER))
    return render_page(
        title="Folha X - Acompanhamento",
        heading="Acompanhamento",
        subtitle="Folha X · itens em aberto · dados ao vivo do Azure DevOps",
        subtitle_title="Projeto HCM - Senior, time Folha X. Épicos, features e work items (Bug, User Story, Task) fora de Closed/Removed/Done na área do time.",
        toolbar=TOOLBAR_HTML,
        body=BODY_HTML,
        css=CSS,
        js=js,
    )


def main():
    write_html(OUTPUT_FILE, generate_html(), "Dashboard Folha X - Acompanhamento")


if __name__ == "__main__":
    main()
