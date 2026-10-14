"""
Dashboard Período - Folha X (Abertas x Fechadas) - DINÂMICO
===========================================================
Gera um dashboard HTML totalmente dinâmico: os dados são buscados
diretamente do Azure DevOps PELO NAVEGADOR (JavaScript), usando um
Personal Access Token informado uma única vez e salvo no localStorage.

Mostra, para o período escolhido, quantos itens foram abertos (criados) e
fechados, com gráfico semanal, quebra por tipo de work item e a lista de
itens. As datas padrão (últimos 30 dias até hoje) são calculadas no
navegador ao abrir a página, e as datas de criação/fechamento são
convertidas para o fuso local antes de agrupar.

Alterar o tipo de work item apenas re-filtra o que já foi carregado;
alterar o período exige clicar em "Atualizar dados".

Não é necessário rodar este script sempre que os dados mudarem — basta
abrir o HTML gerado e clicar em "Atualizar dados". Rode o script de
novo apenas se quiser alterar o layout/comportamento do dashboard.

Uso:
    python dashboard_periodo.py
"""

import json

from ado_common import AREA_PATH, render_page, write_html

OUTPUT_FILE = "dashboard_periodo.html"

WORK_ITEM_TYPES = ["Bug", "User Story", "Task", "Feature", "Epic"]
DEFAULT_DAYS_BACK = 30

CSS = """
.types-box { display:flex; flex-wrap:wrap; gap:4px; }
.type-chip { padding:4px 9px; border:1px solid var(--line); border-radius:12px; font-size:0.75rem; color:var(--muted); background:#fff; cursor:pointer; user-select:none; white-space:nowrap; }
.type-chip input { display:none; }
.type-chip:hover { border-color:var(--brand); }
.type-chip.checked { background:var(--brand-soft); border-color:var(--brand); color:var(--brand); font-weight:600; }
.period-hint { font-size:0.75rem; color:var(--warn); white-space:nowrap; }
.period-hint[hidden] { display:none; }

.kpi.opened .n { color:var(--doing); }
.kpi.closed .n { color:var(--done); }

.grid2.periodo { grid-template-columns:1.4fr 1fr; }
.card h3 .muted { margin-left:6px; }
.card .legend { margin:-4px 0 8px; }
.chart-wrap { position:relative; height:280px; }
.tbl-wrap.scroll { max-height:420px; overflow-y:auto; }
.tbl-wrap.scroll th { position:sticky; top:0; background:var(--card); }
td .type { margin-right:6px; }
td.date { white-space:nowrap; font-variant-numeric:tabular-nums; }
td.title { min-width:260px; }
@media (max-width:900px) { .grid2.periodo { grid-template-columns:1fr; } }
"""

JS_TEMPLATE = r"""
// ============================================================
// Dashboard Período (Abertas x Fechadas)
// ============================================================
const ALL_TYPES = __TYPES_JSON__;
const DEFAULT_DAYS_BACK = __DAYS_BACK_JSON__;
const COLOR_OPEN = "#1565c0";   // --doing
const COLOR_CLOSED = "#2e7d32"; // --done

let ITEMS = [];
let loaded = false;          // já houve uma carga com sucesso?
let loadedPeriod = null;     // período da última carga ({start, end})
let chartInstance = null;

const startInput = document.getElementById("startDate");
const endInput = document.getElementById("endDate");

// Datas padrão calculadas ao abrir a página (não ficam velhas no HTML).
(function setDefaultDates() {
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - DEFAULT_DAYS_BACK);
  endInput.value = localIsoDate(today);
  startInput.value = localIsoDate(start);
})();

// Alterar o período não busca dados sozinho: avisa que é preciso atualizar.
function updatePeriodHint() {
  const changed = loadedPeriod && (startInput.value !== loadedPeriod.start || endInput.value !== loadedPeriod.end);
  document.getElementById("periodHint").hidden = !changed;
}
startInput.addEventListener("change", updatePeriodHint);
endInput.addEventListener("change", updatePeriodHint);

// ISO (UTC) -> data local YYYY-MM-DD, para não jogar itens criados à noite no dia seguinte.
function toLocalDay(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d) ? null : localIsoDate(d);
}

// YYYY-MM-DD -> DD/MM/AAAA
function fmtDay(day) {
  if (!day) return "";
  const [y, m, d] = day.split("-");
  return `${d}/${m}/${y}`;
}

// ============================================================
// Chips de tipo (re-filtram sem nova busca)
// ============================================================
const typesBox = document.getElementById("typesBox");
function renderTypeChips() {
  let html = `<label class="type-chip checked" data-all="1"><input type="checkbox" value="__ALL__" checked>Todos</label>`;
  ALL_TYPES.forEach(t => {
    html += `<label class="type-chip checked" data-type="${escapeHtml(t)}"><input type="checkbox" value="${escapeHtml(t)}" checked>${escapeHtml(t)}</label>`;
  });
  typesBox.innerHTML = html;

  typesBox.querySelectorAll(".type-chip").forEach(chip => {
    chip.addEventListener("click", (e) => {
      if (e.target.tagName !== "INPUT") {
        e.preventDefault();
        const input = chip.querySelector("input");
        input.checked = !input.checked;
      }
      if (chip.dataset.all) {
        const checked = chip.querySelector("input").checked;
        typesBox.querySelectorAll(".type-chip:not([data-all])").forEach(c => {
          c.querySelector("input").checked = checked;
          c.classList.toggle("checked", checked);
        });
      } else {
        const allChip = typesBox.querySelector("[data-all]");
        const allChecked = [...typesBox.querySelectorAll(".type-chip:not([data-all]) input")].every(i => i.checked);
        allChip.querySelector("input").checked = allChecked;
        allChip.classList.toggle("checked", allChecked);
      }
      chip.classList.toggle("checked", chip.querySelector("input").checked);
      renderAll();
    });
  });
}
renderTypeChips();

function getSelectedTypes() {
  return [...typesBox.querySelectorAll(".type-chip:not([data-all]) input:checked")].map(i => i.value);
}

// ============================================================
// WIQL / links para o Azure DevOps
// ============================================================
function buildWiql(dateField, start, end, types) {
  const typesClause = types.map(t => `'${wiqlStr(t)}'`).join(", ");
  return `SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo] FROM WorkItems WHERE [System.TeamProject] = '${wiqlStr(ADO_PROJECT)}' AND [System.WorkItemType] IN (${typesClause}) AND [System.AreaPath] UNDER '${wiqlStr(AREA_PATH)}' AND [${dateField}] >= '${start}' AND [${dateField}] <= '${end}' ORDER BY [${dateField}] DESC`;
}

// ============================================================
// Gráfico semanal
// ============================================================
function generateBuckets(startStr, endStr) {
  const buckets = [];
  let current = new Date(startStr + "T00:00:00");
  const endDate = new Date(endStr + "T00:00:00");
  const ddmm = d => d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  while (current <= endDate) {
    const bucketEnd = new Date(current);
    bucketEnd.setDate(bucketEnd.getDate() + 6);
    const actualEnd = bucketEnd > endDate ? endDate : bucketEnd;
    buckets.push({ start: localIsoDate(current), end: localIsoDate(actualEnd), label: `${ddmm(current)}-${ddmm(actualEnd)}` });
    current = new Date(actualEnd);
    current.setDate(current.getDate() + 1);
  }
  return buckets;
}

function renderChart(filteredOpen, filteredClosed, start, end) {
  const buckets = generateBuckets(start, end);
  const openData = buckets.map(b => filteredOpen.filter(it => it.created >= b.start && it.created <= b.end).length);
  const closedData = buckets.map(b => filteredClosed.filter(it => it.closed >= b.start && it.closed <= b.end).length);

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = "#6b7280";
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(document.getElementById("chartPeriodo"), {
    type: "bar",
    data: {
      labels: buckets.map(b => b.label),
      datasets: [
        { label: "Abertas", data: openData, backgroundColor: COLOR_OPEN, borderRadius: 3, maxBarThickness: 28 },
        { label: "Fechadas", data: closedData, backgroundColor: COLOR_CLOSED, borderRadius: 3, maxBarThickness: 28 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#f0f1f3" }, border: { display: false } },
        x: { grid: { display: false }, ticks: { maxRotation: 45 } },
      },
    },
  });
}

// ============================================================
// Tabela por tipo
// ============================================================
function renderBreakdown(filteredOpen, filteredClosed, selectedTypes, start, end) {
  const rows = selectedTypes.map(t => ({
    type: t,
    abertas: filteredOpen.filter(it => it.type === t).length,
    fechadas: filteredClosed.filter(it => it.type === t).length,
    urlOpen: queryUrl(buildWiql("System.CreatedDate", start, end, [t])),
    urlClosed: queryUrl(buildWiql("Microsoft.VSTS.Common.ClosedDate", start, end, [t])),
  })).filter(r => r.abertas > 0 || r.fechadas > 0);

  const tbody = document.getElementById("breakdownBody");
  const tfoot = document.getElementById("breakdownFoot");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Nenhum item no período/tipo selecionado.</td></tr>`;
    tfoot.innerHTML = "";
    return;
  }
  tbody.innerHTML = rows.map(r => `<tr>
    <td>${typeMark(r.type)}${escapeHtml(r.type)}</td>
    <td class="num"><a href="${r.urlOpen}" target="_blank" title="Abrir consulta no Azure DevOps">${r.abertas}</a></td>
    <td class="num"><a href="${r.urlClosed}" target="_blank" title="Abrir consulta no Azure DevOps">${r.fechadas}</a></td>
    <td class="num">${r.abertas - r.fechadas}</td>
  </tr>`).join("");
  const tOpen = rows.reduce((s, r) => s + r.abertas, 0);
  const tClosed = rows.reduce((s, r) => s + r.fechadas, 0);
  tfoot.innerHTML = `<tr><td>Total</td><td class="num">${tOpen}</td><td class="num">${tClosed}</td><td class="num">${tOpen - tClosed}</td></tr>`;
}

// ============================================================
// Lista de itens
// ============================================================
function renderItemsTable(filteredOpen, filteredClosed) {
  const byId = new Map();
  filteredOpen.forEach(it => byId.set(it.id, it));
  filteredClosed.forEach(it => byId.set(it.id, it));
  const combined = [...byId.values()].sort((a, b) => (b.closed || b.created || "").localeCompare(a.closed || a.created || ""));

  document.getElementById("itemsCount").textContent = combined.length ? `${combined.length} itens` : "";
  const tbody = document.getElementById("itemsBody");
  if (!combined.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Nenhum item no período/tipo selecionado.</td></tr>`;
    return;
  }
  tbody.innerHTML = combined.map(it => `<tr>
    <td><a href="${workItemUrl(it.id)}" target="_blank">${it.id}</a></td>
    <td class="title">${typeMark(it.type)}${escapeHtml(it.title)}</td>
    <td>${stateLabel(it.state)}</td>
    <td>${escapeHtml(it.assignee)}</td>
    <td class="date">${fmtDay(it.created) || "-"}</td>
    <td class="date">${it.closed ? fmtDay(it.closed) : '<span class="muted">em aberto</span>'}</td>
  </tr>`).join("");
}

// ============================================================
// Renderização (a partir dos dados já carregados em ITEMS)
// ============================================================
function renderAll() {
  if (!loaded) return;
  // Usa o período efetivamente carregado (mudar as datas exige Atualizar).
  const { start, end } = loadedPeriod;
  const selectedTypes = getSelectedTypes();

  const filteredOpen = ITEMS.filter(it => selectedTypes.includes(it.type) && it.created && it.created >= start && it.created <= end);
  const filteredClosed = ITEMS.filter(it => selectedTypes.includes(it.type) && it.closed && it.closed >= start && it.closed <= end);

  const saldo = filteredOpen.length - filteredClosed.length;
  document.getElementById("nAbertas").textContent = filteredOpen.length;
  document.getElementById("nFechadas").textContent = filteredClosed.length;
  document.getElementById("nSaldo").textContent = saldo > 0 ? `+${saldo}` : saldo;
  const kpiSaldo = document.getElementById("kpiSaldo");
  kpiSaldo.classList.toggle("warn", saldo > 0);
  kpiSaldo.classList.toggle("good", saldo <= 0);

  document.getElementById("kpiAbertas").href = queryUrl(buildWiql("System.CreatedDate", start, end, selectedTypes));
  document.getElementById("kpiFechadas").href = queryUrl(buildWiql("Microsoft.VSTS.Common.ClosedDate", start, end, selectedTypes));

  renderBreakdown(filteredOpen, filteredClosed, selectedTypes, start, end);
  renderChart(filteredOpen, filteredClosed, start, end);
  renderItemsTable(filteredOpen, filteredClosed);
}

// ============================================================
// Atualizar dados (busca no Azure DevOps)
// ============================================================
async function refreshData() {
  const start = startInput.value;
  const end = endInput.value;
  if (!start || !end || start > end) {
    throw new Error("Informe um período válido (data inicial <= data final).");
  }

  setStatus("Carregando dados do Azure DevOps...", "");
  try {
    const typesClause = ALL_TYPES.map(t => `'${wiqlStr(t)}'`).join(", ");
    // A API WIQL usa precisão de data (sem horário) por padrão: passar um
    // horário junto da data (ex: T23:59:59Z) causa erro HTTP 400
    // ("You cannot supply a time with the date..."). Por isso usamos
    // apenas YYYY-MM-DD aqui.
    const query = `SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '${wiqlStr(ADO_PROJECT)}' AND [System.WorkItemType] IN (${typesClause}) AND [System.AreaPath] UNDER '${wiqlStr(AREA_PATH)}' AND ( ([System.CreatedDate] >= '${start}' AND [System.CreatedDate] <= '${end}') OR ([Microsoft.VSTS.Common.ClosedDate] >= '${start}' AND [Microsoft.VSTS.Common.ClosedDate] <= '${end}') )`;
    const ids = await wiql(query, "itens criados/fechados no período");

    const fields = ["System.Id", "System.Title", "System.WorkItemType", "System.State", "System.AssignedTo", "System.CreatedDate", "Microsoft.VSTS.Common.ClosedDate"];
    const raw = ids.length ? await getWorkItemsBatch(ids, fields) : [];

    ITEMS = raw.map(wi => {
      const f = wi.fields;
      return {
        id: f["System.Id"],
        title: f["System.Title"] || "",
        type: f["System.WorkItemType"] || "",
        state: f["System.State"] || "",
        assignee: extractName(f["System.AssignedTo"]),
        created: toLocalDay(f["System.CreatedDate"]),
        closed: toLocalDay(f["Microsoft.VSTS.Common.ClosedDate"]),
      };
    });

    loaded = true;
    loadedPeriod = { start, end };
    updatePeriodHint();
    renderAll();
    finishStatus(`Atualizado: ${ITEMS.length} itens de ${fmtDay(start)} a ${fmtDay(end)} carregados às ${new Date().toLocaleTimeString("pt-BR")}.`);
  } catch (err) {
    const msg = `<tr><td colspan="6" class="empty-state">Falha ao carregar dados: ${escapeHtml(err.message)}</td></tr>`;
    document.getElementById("itemsBody").innerHTML = msg;
    throw err;
  }
}

initDashboard(refreshData);
"""

TOOLBAR_HTML = """<label class="field" title="Alterar o período exige clicar em Atualizar dados">De <input type="date" id="startDate"></label>
    <label class="field" title="Alterar o período exige clicar em Atualizar dados">até <input type="date" id="endDate"></label>
    <span class="period-hint" id="periodHint" hidden>Período alterado: clique em Atualizar dados</span>
    <span class="spacer"></span>
    <div class="types-box" id="typesBox" title="Filtra os dados já carregados, sem nova busca"></div>
"""

BODY_HTML = """  <div class="kpis">
    <a class="kpi opened" id="kpiAbertas" href="#" target="_blank" title="Abrir consulta no Azure DevOps">
      <div class="n" id="nAbertas">-</div>
      <div class="l">abertas no período ↗</div>
    </a>
    <a class="kpi closed" id="kpiFechadas" href="#" target="_blank" title="Abrir consulta no Azure DevOps">
      <div class="n" id="nFechadas">-</div>
      <div class="l">fechadas no período ↗</div>
    </a>
    <div class="kpi" id="kpiSaldo">
      <div class="n" id="nSaldo">-</div>
      <div class="l">saldo (abertas − fechadas)</div>
    </div>
  </div>

  <div class="grid2 periodo">
    <div class="card">
      <h3>Abertas x fechadas por semana</h3>
      <div class="legend">
        <span><i class="seg-doing"></i>Abertas (criadas)</span>
        <span><i class="seg-done"></i>Fechadas</span>
      </div>
      <div class="chart-wrap"><canvas id="chartPeriodo"></canvas></div>
    </div>
    <div class="card">
      <h3>Por tipo de work item</h3>
      <div class="tbl-wrap scroll">
        <table>
          <thead><tr><th>Tipo</th><th class="num">Abertas</th><th class="num">Fechadas</th><th class="num">Saldo</th></tr></thead>
          <tbody id="breakdownBody"><tr><td colspan="4" class="empty-state">Clique em "Atualizar dados" para carregar.</td></tr></tbody>
          <tfoot id="breakdownFoot"></tfoot>
        </table>
      </div>
    </div>
  </div>

  <div class="card">
    <h3>Itens do período <span class="muted" id="itemsCount"></span></h3>
    <div class="tbl-wrap scroll">
      <table>
        <thead><tr><th>ID</th><th>Título</th><th>Estado</th><th>Responsável</th><th>Criado</th><th>Fechado</th></tr></thead>
        <tbody id="itemsBody"><tr><td colspan="6" class="empty-state">Configure o PAT (⚙) e clique em "Atualizar dados" para carregar.</td></tr></tbody>
      </table>
    </div>
  </div>
"""


def generate_html():
    js = (
        JS_TEMPLATE
        .replace("__TYPES_JSON__", json.dumps(WORK_ITEM_TYPES))
        .replace("__DAYS_BACK_JSON__", json.dumps(DEFAULT_DAYS_BACK))
    )
    return render_page(
        title="Folha X - Abertas x Fechadas por Período",
        heading="Abertas x Fechadas",
        subtitle="Itens criados e fechados no período · dados ao vivo do Azure DevOps",
        subtitle_title=(
            f"Área: {AREA_PATH}. Tipos: {', '.join(WORK_ITEM_TYPES)}. "
            "Datas convertidas para o fuso local. Alterar o período requer "
            "Atualizar dados; alterar o tipo apenas re-filtra o que já foi carregado."
        ),
        toolbar=TOOLBAR_HTML,
        body=BODY_HTML,
        css=CSS,
        js=js,
        use_chartjs=True,
    )


def main():
    write_html(OUTPUT_FILE, generate_html(), "Dashboard Período (Abertas x Fechadas)")


if __name__ == "__main__":
    main()
