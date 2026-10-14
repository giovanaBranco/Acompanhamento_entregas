"""
Peças compartilhadas pelos geradores dashboard_*.py
====================================================
- Configuração do Azure DevOps (organização, projeto, time, área).
- Cliente JavaScript do Azure DevOps embutido em cada HTML (PAT no
  localStorage, WIQL, batch de work items, escape de HTML e avisos de
  carga incompleta).
- CSS base e estrutura de página (cabeçalho, barra de ferramentas,
  configuração do PAT), para que todos os dashboards tenham o mesmo visual.

Cada HTML gerado continua autocontido: este módulo só é usado na geração.
"""

import html
import json
import os
import sys

ORGANIZATION = "senior-sistemas"
PROJECT = "HCM - Senior"
TEAM = "Folha X"
AREA_PATH = "HCM - Senior\\Folha X"

CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"


def configure_stdout():
    """Garante UTF-8 na saída: os prints usam emojis/acentos que quebram no
    console padrão do Windows (cp1252) com UnicodeEncodeError."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


# =============================================================================
# CSS base (mesmo visual do dashboard de Releases)
# =============================================================================
BASE_CSS = r"""
:root {
  --ink:#1f2430; --muted:#6b7280; --faint:#9ca3af; --line:#e5e7eb; --bg:#f4f5f7; --card:#fff;
  --brand:#1a237e; --brand-soft:#eef0fb;
  --done:#2e7d32; --test:#7b1fa2; --doing:#1565c0; --todo:#c7cbd3; --bug:#c62828; --warn:#e65100;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI', Tahoma, Verdana, sans-serif; background:var(--bg); color:var(--ink); padding:20px; font-size:14px; }
.wrap { max-width:1300px; margin:0 auto; }
a { color:var(--brand); text-decoration:none; }
a:hover { text-decoration:underline; }

header.page { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
header.page h1 { font-size:1.35rem; color:var(--brand); }
header.page p { color:var(--muted); font-size:0.8rem; }

.toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; background:var(--card); padding:10px 12px; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
.toolbar input[type=text], .toolbar input[type=number], .toolbar input[type=date] { padding:7px 10px; border:1px solid var(--line); border-radius:6px; font-size:0.85rem; font-family:inherit; }
.toolbar input[type=text] { flex:1; min-width:200px; }
.toolbar input[type=number] { width:90px; }
.toolbar select { padding:7px 8px; border:1px solid var(--line); border-radius:6px; font-size:0.85rem; background:#fff; max-width:220px; }
.toolbar .field { display:flex; align-items:center; gap:6px; font-size:0.8rem; color:var(--muted); }
.toolbar .check { display:flex; align-items:center; gap:5px; font-size:0.8rem; color:var(--muted); cursor:pointer; white-space:nowrap; }
.toolbar .spacer { flex:0 0 1px; height:22px; background:var(--line); margin:0 2px; }
.toolbar .grow { flex:1; }
.btn { padding:7px 12px; border:1px solid var(--line); border-radius:6px; font-size:0.8rem; font-weight:600; cursor:pointer; background:#fff; color:var(--ink); font-family:inherit; }
.btn:hover { border-color:var(--brand); color:var(--brand); }
.btn:disabled { background:#eee; color:#999; cursor:wait; }
.btn-primary { background:var(--brand); border-color:var(--brand); color:#fff; }
.btn-primary:hover { background:#131a5e; color:#fff; }

.pat-settings { position:relative; }
.pat-settings summary { cursor:pointer; list-style:none; padding:6px 9px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--muted); user-select:none; }
.pat-settings summary::-webkit-details-marker { display:none; }
.pat-settings summary:hover, .pat-settings[open] summary { color:var(--brand); border-color:var(--brand); }
.pat-settings-body { position:absolute; top:calc(100% + 6px); right:0; z-index:20; background:#fff; border:1px solid var(--line); border-radius:10px; box-shadow:0 4px 16px rgba(0,0,0,0.15); padding:14px 16px; display:flex; flex-direction:column; gap:10px; width:340px; }
.pat-settings-body label { font-size:0.76rem; color:#555; display:flex; flex-direction:column; gap:4px; }
.pat-settings-body input[type=password] { padding:7px 9px; border:1px solid #ccc; border-radius:6px; font-size:0.82rem; width:100%; }
.pat-settings-body small { color:var(--muted); font-size:0.7rem; }

.refresh-status { display:block; min-height:1.2em; margin:6px 2px 12px; font-size:0.75rem; color:var(--muted); }
.refresh-status.ok { color:var(--done); }
.refresh-status.err { color:#c62828; font-weight:600; }

.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:10px; margin-bottom:14px; }
.kpi { background:var(--card); border-radius:10px; padding:12px 16px; box-shadow:0 1px 3px rgba(0,0,0,0.06); display:flex; flex-direction:column; justify-content:center; color:inherit; }
a.kpi:hover { text-decoration:none; box-shadow:0 0 0 1px var(--brand); }
.kpi .n { font-size:1.6rem; font-weight:800; color:var(--brand); line-height:1.1; }
.kpi .l { font-size:0.75rem; color:var(--muted); margin-top:2px; }
.kpi.good .n { color:var(--done); }
.kpi.warn .n { color:var(--warn); }
.kpi-counts { display:flex; gap:22px; flex-wrap:wrap; }
.kpi-counts div b { display:block; font-size:1.25rem; color:var(--ink); }
.kpi-counts div span { font-size:0.75rem; color:var(--muted); }

.card { background:var(--card); border-radius:10px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:14px; }
.card h3 { font-size:0.9rem; color:var(--ink); margin-bottom:12px; font-weight:700; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.grid2 > .card { margin-bottom:0; }
.grid2 + * { margin-top:14px; }
.section-title { font-size:1rem; font-weight:700; margin:22px 4px 10px; display:flex; align-items:center; gap:10px; }
.section-title .count, .muted { font-size:0.78rem; color:var(--muted); font-weight:400; }
.note { font-size:0.75rem; color:var(--muted); margin-top:8px; line-height:1.45; }

.tbl-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:0.82rem; }
th { text-align:left; font-weight:600; color:var(--muted); font-size:0.75rem; padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
td { padding:7px 10px; border-bottom:1px solid #f0f1f3; }
tbody tr:hover { background:#f7f8fa; }
tfoot td { font-weight:700; border-top:1px solid var(--line); border-bottom:none; }
.num { text-align:right; font-variant-numeric:tabular-nums; }
.cell-warn { background:#fff8e1; }
.cell-alert { background:#ffebee; color:#b71c1c; }

.empty-state { text-align:center; color:var(--faint); padding:40px; font-size:0.9rem; }
.empty-row { font-size:0.8rem; color:var(--faint); padding:8px; list-style:none; }

.legend { display:flex; gap:14px; flex-wrap:wrap; font-size:0.75rem; color:var(--muted); margin:0 2px 14px; }
.legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }

.bar { display:flex; height:8px; border-radius:4px; overflow:hidden; background:var(--todo); }
.bar span { display:block; height:100%; }
.seg-done { background:var(--done); }
.seg-test { background:var(--test); }
.seg-doing { background:var(--doing); }
.seg-todo { background:var(--todo); }

.state { font-size:0.78rem; color:var(--muted); white-space:nowrap; }
.state::before { content:""; display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; background:var(--todo); vertical-align:1px; }
.state.s-done::before { background:var(--done); }
.state.s-test::before { background:var(--test); }
.state.s-doing::before { background:var(--doing); }
.state.s-removed::before { background:transparent; border:1px solid var(--faint); }

.type { display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:16px; padding:0 3px; border-radius:3px; font-size:0.62rem; font-weight:700; color:#fff; flex:0 0 auto; }
.type-epic { background:#5e35b1; }
.type-feature { background:#00897b; }
.type-story { background:#1e88e5; }
.type-bug { background:var(--bug); }
.type-task { background:#9e9e9e; }

.collapsible { background:var(--card); border-radius:8px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
.collapsible > .head { display:flex; align-items:center; gap:10px; padding:10px 16px; cursor:pointer; }
.collapsible > .head:hover { background:#fafbfd; }
.collapsible > .body { display:none; border-top:1px solid var(--line); padding:8px 16px 12px; }
.collapsible.open > .body { display:block; }
.chev { color:var(--faint); font-size:0.75rem; transition:transform 0.15s; display:inline-block; }
.collapsible.open > .head .chev { transform:rotate(90deg); }

.footer { text-align:center; color:var(--faint); font-size:0.72rem; margin-top:24px; }

@media (max-width:900px) {
  .grid2 { grid-template-columns:1fr; }
}
"""


# =============================================================================
# Cliente Azure DevOps (JavaScript)
# =============================================================================
ADO_CLIENT_JS = r"""
// ============================================================
// Cliente Azure DevOps (gerado por ado_common.py)
// ============================================================
const ADO_ORG = __ORG_JSON__;
const ADO_PROJECT = __PROJECT_JSON__;
const ADO_TEAM = __TEAM_JSON__;
const AREA_PATH = __AREA_PATH_JSON__;
const PAT_KEY = "ado_dashboard_pat";
const WIQL_MAX = 20000;  // limite máximo de resultados da API WIQL

// Avisos de carga incompleta (resultado truncado, lote com erro etc.),
// exibidos ao final da atualização em vez de serem engolidos.
let loadWarnings = [];

function getPat() { return localStorage.getItem(PAT_KEY) || ""; }
function adoHeaders() { return { "Authorization": "Basic " + btoa(":" + getPat()), "Content-Type": "application/json" }; }
function adoBase() { return `https://dev.azure.com/${ADO_ORG}/${encodeURIComponent(ADO_PROJECT)}`; }

async function adoError(resp, what) {
  let detail = "";
  try { detail = (await resp.json()).message || ""; } catch (e) { /* corpo não era JSON */ }
  return new Error(`${what} falhou (HTTP ${resp.status})${detail ? ": " + detail : (resp.status === 401 || resp.status === 403 ? ". Verifique o PAT." : ".")}`);
}

// Retorna o JSON completo da consulta WIQL (útil para WorkItemLinks).
async function wiqlRaw(query, label) {
  const url = `${adoBase()}/${encodeURIComponent(ADO_TEAM)}/_apis/wit/wiql?api-version=7.1&$top=${WIQL_MAX}`;
  const resp = await fetch(url, { method: "POST", headers: adoHeaders(), body: JSON.stringify({ query }) });
  if (!resp.ok) throw await adoError(resp, "Consulta WIQL" + (label ? ` (${label})` : ""));
  const data = await resp.json();
  const n = (data.workItems || data.workItemRelations || []).length;
  if (n >= WIQL_MAX) {
    loadWarnings.push(`${label || "consulta"}: resultado atingiu o limite de ${WIQL_MAX} itens e pode estar incompleto`);
  }
  return data;
}

// Retorna só os IDs da consulta WIQL.
async function wiql(query, label) {
  const data = await wiqlRaw(query, label);
  return (data.workItems || []).map(wi => wi.id);
}

async function getWorkItemsBatch(ids, fields) {
  const all = [];
  for (let i = 0; i < ids.length; i += 200) {
    const batch = ids.slice(i, i + 200);
    const resp = await fetch(`${adoBase()}/_apis/wit/workitemsbatch?api-version=7.1`, { method: "POST", headers: adoHeaders(), body: JSON.stringify({ ids: batch, fields }) });
    if (!resp.ok) throw await adoError(resp, "Busca de work items");
    const data = await resp.json();
    all.push(...(data.value || []));
  }
  return all;
}

// IDs dos filhos (de certos tipos) de vários pais, em lotes de 500.
// Um lote com erro vira aviso e não interrompe a carga.
async function queryChildrenOfMany(parentIds, types, extraClause) {
  if (!parentIds.length) return [];
  const typesClause = types.map(t => `'${wiqlStr(t)}'`).join(", ");
  let allIds = [];
  for (let i = 0; i < parentIds.length; i += 500) {
    const batch = parentIds.slice(i, i + 500);
    const query = `SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '${wiqlStr(ADO_PROJECT)}' AND [System.WorkItemType] IN (${typesClause}) AND [System.Parent] IN (${batch.map(Number).join(", ")}) ${extraClause || ""}`;
    const label = `filhos ${types.join("/")} (lote ${i / 500 + 1})`;
    try {
      allIds = allIds.concat(await wiql(query, label));
    } catch (e) {
      loadWarnings.push(`${label}: ${e.message}`);
    }
  }
  return allIds;
}

// Executa fn(item) para cada item com no máximo `limit` chamadas simultâneas.
async function runWithConcurrency(items, limit, fn) {
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const item = items[next++];
      await fn(item);
    }
  }
  const workers = [];
  for (let w = 0; w < Math.min(limit, items.length); w++) workers.push(worker());
  await Promise.all(workers);
}

function extractName(field) {
  if (!field) return "Não atribuído";
  if (typeof field === "object") return field.displayName || "Não atribuído";
  return String(field);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Escapa um texto para uso dentro de uma string WIQL ('...').
function wiqlStr(s) { return String(s ?? "").replace(/'/g, "''"); }

function stripHtml(text) {
  let t = (text || "").replace(/<[^>]+>/g, " ");
  t = t.replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
  return t.replace(/\s+/g, " ").trim();
}

function workItemUrl(id) { return `${adoBase()}/_workitems/edit/${id}`; }
function queryUrl(wiqlText) { return `${adoBase()}/_workitems?_a=query&wiql=${encodeURIComponent(wiqlText)}`; }

const CLOSED_LIKE = new Set(["Closed", "Done", "Resolved"]);
const TEST_LIKE = new Set(["Test", "Review"]);
const DOING_LIKE = new Set(["Active"]);
const IGNORED_STATES = new Set(["Removed"]);

function stateGroup(state) {
  if (CLOSED_LIKE.has(state)) return "done";
  if (TEST_LIKE.has(state)) return "test";
  if (DOING_LIKE.has(state)) return "doing";
  if (IGNORED_STATES.has(state)) return "removed";
  return "todo";
}
function stateLabel(state) { return `<span class="state s-${stateGroup(state)}">${escapeHtml(state)}</span>`; }

const TYPE_MARKS = {
  "Epic": ["E", "type-epic"], "Feature": ["F", "type-feature"], "User Story": ["US", "type-story"],
  "Bug": ["B", "type-bug"], "Task": ["T", "type-task"],
};
function typeMark(type) {
  const [label, cls] = TYPE_MARKS[type] || [(type || "?").slice(0, 2), "type-task"];
  return `<span class="type ${cls}" title="${escapeHtml(type)}">${label}</span>`;
}

function round1(x) { return Math.round((x || 0) * 10) / 10; }
function median(sortedValues) {
  const v = sortedValues, n = v.length;
  if (!n) return 0;
  return n % 2 ? v[(n - 1) / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;
}

// Data local (não UTC) no formato YYYY-MM-DD.
function localIsoDate(d) {
  const p = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function setStatus(msg, cls) {
  const el = document.getElementById("refreshStatus");
  el.textContent = msg;
  el.className = "refresh-status " + (cls || "");
}

// Mensagem final da atualização: sinaliza em vermelho se houve avisos.
function finishStatus(doneMsg) {
  if (loadWarnings.length) {
    console.warn("Avisos de carga:", loadWarnings);
    setStatus(`${doneMsg} ⚠️ Dados possivelmente incompletos (${loadWarnings.length} aviso(s)): ${loadWarnings.slice(0, 3).join("; ")}${loadWarnings.length > 3 ? "; ..." : ""}`, "err");
  } else {
    setStatus(doneMsg, "ok");
  }
}

// Liga o campo de PAT (⚙) e o botão Atualizar; carrega automaticamente se já houver PAT.
function initDashboard(refreshFn) {
  const patInput = document.getElementById("patInput");
  patInput.value = getPat();
  document.getElementById("btnSavePat").addEventListener("click", () => {
    localStorage.setItem(PAT_KEY, patInput.value.trim());
    document.querySelector(".pat-settings").removeAttribute("open");
    setStatus("PAT salvo neste navegador.", "ok");
  });
  document.getElementById("btnRefresh").addEventListener("click", async () => {
    if (!getPat()) {
      setStatus("Configure o PAT (⚙) antes de atualizar.", "err");
      document.querySelector(".pat-settings").setAttribute("open", "");
      return;
    }
    const btn = document.getElementById("btnRefresh");
    btn.disabled = true;
    loadWarnings = [];
    try {
      await refreshFn();
    } catch (err) {
      console.error(err);
      setStatus("Erro ao atualizar: " + err.message, "err");
    } finally {
      btn.disabled = false;
    }
  });
  if (getPat()) document.getElementById("btnRefresh").click();
  else setStatus("Configure o PAT (⚙) e clique em Atualizar dados.", "");
}
"""


def pat_settings_html(scope="Work Items (Read)"):
    return f"""<details class="pat-settings">
      <summary title="Configurar PAT do Azure DevOps">⚙</summary>
      <div class="pat-settings-body">
        <label>Azure DevOps PAT
          <input type="password" id="patInput" placeholder="cole seu PAT com escopo {scope}">
        </label>
        <button class="btn" id="btnSavePat">Salvar no navegador</button>
        <small>O token fica salvo apenas no localStorage deste navegador (mesmo PAT usado nos demais dashboards do portal).</small>
      </div>
    </details>"""


def render_page(*, title, heading, subtitle, toolbar, body, css="", js="",
                refresh_label="Atualizar dados", pat_scope="Work Items (Read)",
                subtitle_title="", use_chartjs=False):
    """Monta o HTML completo de um dashboard.

    `toolbar` é o HTML dos filtros (à esquerda); o ⚙ do PAT e o botão de
    atualizar são acrescentados à direita. `js` é o script específico do
    dashboard e deve chamar initDashboard(refreshData) no final."""
    head_extra = f'<script src="{CHART_JS_URL}"></script>\n' if use_chartjs else ""
    client_js = (
        ADO_CLIENT_JS
        .replace("__ORG_JSON__", json.dumps(ORGANIZATION))
        .replace("__PROJECT_JSON__", json.dumps(PROJECT))
        .replace("__TEAM_JSON__", json.dumps(TEAM))
        .replace("__AREA_PATH_JSON__", json.dumps(AREA_PATH))
    )
    sub_title_attr = f' title="{html.escape(subtitle_title, quote=True)}"' if subtitle_title else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{head_extra}<style>{BASE_CSS}{css}</style>
</head>
<body>
<div class="wrap">
  <header class="page">
    <h1>{heading}</h1>
    <p{sub_title_attr}>{subtitle}</p>
  </header>

  <div class="toolbar">
    {toolbar}
    <span class="grow"></span>
    {pat_settings_html(pat_scope)}
    <button class="btn btn-primary" id="btnRefresh">{refresh_label}</button>
  </div>
  <span class="refresh-status" id="refreshStatus"></span>

{body}
</div>
<script>{client_js}</script>
<script>{js}</script>
</body>
</html>"""


def write_html(output_file, page_html, label):
    configure_stdout()
    print("=" * 60)
    print(f"  {label} - DINÂMICO")
    print("=" * 60)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"\n✅ Dashboard (shell dinâmico) gerado: {os.path.abspath(output_file)}")
    print("   Abra o arquivo no navegador (ou pelo index.html) e configure o PAT no ⚙.")
