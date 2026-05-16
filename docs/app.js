// Scenario page renderer. Reads <meta name="scenario-slug"> from the host
// page, fetches ../data/<slug>.json, and renders the three Plotly charts plus
// a summary table. Generic over scenarios — labels and break-even references
// come from DATA.scenario, not the page.

let DATA = null;

const fmtPct = (x) => `${(x * 100).toFixed(2)}%`;
const fmtDollar = (x) =>
  `$${x.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

function scenarioSlug() {
  const meta = document.querySelector('meta[name="scenario-slug"]');
  if (!meta) throw new Error('Missing <meta name="scenario-slug"> on this page');
  return meta.getAttribute('content');
}

function dataUrl(slug) {
  // Pages live at docs/scenarios/<page>.html; data lives at docs/data/<slug>.json.
  return `../data/${slug}.json`;
}

async function loadData() {
  const slug = scenarioSlug();
  const resp = await fetch(dataUrl(slug));
  if (!resp.ok) {
    throw new Error(`Failed to load ${dataUrl(slug)}: ${resp.status}`);
  }
  DATA = await resp.json();
  bootstrapPage();
  render();
}

function bootstrapPage() {
  const { scenario } = DATA;

  const blurb = document.getElementById('scenarioBlurb');
  if (blurb) blurb.textContent = scenario.description;

  const horizonSel = document.getElementById('horizon');
  horizonSel.innerHTML = '';
  const horizons = scenario.horizons || Object.keys(DATA.rolling).map(Number);
  const defaultH = horizons.includes(10) ? 10 : Math.max(...horizons);
  for (const h of horizons) {
    const opt = document.createElement('option');
    opt.value = String(h);
    opt.textContent = String(h);
    if (h === defaultH) opt.selected = true;
    horizonSel.appendChild(opt);
  }
  horizonSel.disabled = horizons.length <= 1;

  horizonSel.addEventListener('change', render);
  document.getElementById('returnType').addEventListener('change', render);
}

function selected() {
  return {
    horizon: document.getElementById('horizon').value,
    type: document.getElementById('returnType').value,
  };
}

function render() {
  const { horizon, type } = selected();
  const { scenario } = DATA;
  const rows = DATA.rolling[horizon];
  if (!rows || rows.length === 0) return;

  const metricKey = `${type}_metric`;
  const termKey = `${type}_terminal`;
  const metricName = scenario.metric_name;
  const totalInvested = scenario.total_invested;

  const x = rows.map((r) => r.start);
  const metric = rows.map((r) => r[metricKey]);
  const terminal = rows.map((r) => r[termKey]);

  document.getElementById('cagrHeader').textContent =
    `${horizon}-year rolling ${metricName} (${type})`;
  document.getElementById('histHeader').textContent =
    `Distribution of ${horizon}-year rolling ${metricName} (${type})`;
  document.getElementById('terminalHeader').textContent =
    `Terminal value of ${fmtDollar(totalInvested)} contributed over ${horizon} years`;
  document.getElementById('terminalCaption').textContent =
    `Value at the end of the window. Break-even reference: ${fmtDollar(totalInvested)} total contributed.`;

  const commonLayout = {
    margin: { t: 20, l: 60, r: 20, b: 50 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
  };
  const config = { responsive: true, displaylogo: false };

  Plotly.react(
    'cagrChart',
    [
      {
        x,
        y: metric,
        mode: 'lines',
        name: metricName,
        line: { width: 1.5 },
        hovertemplate: `Start: %{x}<br>${metricName}: %{y:.2%}<extra></extra>`,
      },
    ],
    {
      ...commonLayout,
      yaxis: {
        tickformat: '.0%',
        title: { text: `Annualized return (${metricName})` },
        zeroline: true,
      },
      xaxis: { title: { text: 'Window start date' } },
    },
    config
  );

  Plotly.react(
    'histChart',
    [
      {
        x: metric,
        type: 'histogram',
        nbinsx: 40,
        hovertemplate: 'Bin: %{x:.1%}<br>Count: %{y}<extra></extra>',
      },
    ],
    {
      ...commonLayout,
      xaxis: { tickformat: '.0%', title: { text: `Annualized return (${metricName})` } },
      yaxis: { title: { text: 'Number of windows' } },
    },
    config
  );

  Plotly.react(
    'terminalChart',
    [
      {
        x,
        y: terminal,
        mode: 'lines',
        line: { width: 1.5 },
        hovertemplate: 'Start: %{x}<br>Terminal: $%{y:,.0f}<extra></extra>',
      },
      {
        x: [x[0], x[x.length - 1]],
        y: [totalInvested, totalInvested],
        mode: 'lines',
        line: { width: 1, dash: 'dash', color: 'rgba(0,0,0,0.5)' },
        name: `Break-even (${fmtDollar(totalInvested)})`,
        hoverinfo: 'skip',
      },
    ],
    {
      ...commonLayout,
      yaxis: { title: { text: 'Terminal value ($)' }, tickformat: '$,.0f' },
      xaxis: { title: { text: 'Window start date' } },
      showlegend: true,
    },
    config
  );

  renderStats(rows, horizon, metricName, totalInvested);
}

function renderStats(rows, horizon, metricName, totalInvested) {
  // Summary stats always show both nominal and real side-by-side, regardless
  // of the "Return type" dropdown — the dropdown only affects the charts.
  const compute = (key) => {
    const arr = rows.map((r) => r[key]);
    const n = arr.length;
    const mean = arr.reduce((a, b) => a + b, 0) / n;
    const sorted = [...arr].sort((a, b) => a - b);
    return {
      n,
      mean,
      median: sorted[Math.floor(n / 2)],
      min: sorted[0],
      max: sorted[n - 1],
      minIdx: arr.indexOf(sorted[0]),
      maxIdx: arr.indexOf(sorted[n - 1]),
      negCount: arr.filter((c) => c < 0).length,
    };
  };

  const nom = compute('nominal_metric');
  const real = compute('real_metric');

  const firstRow = rows[0];
  const lastRow = rows[rows.length - 1];

  const bestCell = (s) =>
    `${fmtPct(s.max)}<br><small>${rows[s.maxIdx].start} → ${rows[s.maxIdx].end}</small>`;
  const worstCell = (s) =>
    `${fmtPct(s.min)}<br><small>${rows[s.minIdx].start} → ${rows[s.minIdx].end}</small>`;
  const negCell = (s) =>
    `${s.negCount} (${((s.negCount / s.n) * 100).toFixed(1)}%)`;

  document.getElementById('stats').innerHTML = `
    <table>
      <thead>
        <tr><th>${horizon}-year windows</th><th>Nominal</th><th>Real</th></tr>
      </thead>
      <tbody>
        <tr><td>Number of windows</td><td>${nom.n.toLocaleString()}</td><td>${real.n.toLocaleString()}</td></tr>
        <tr><td>Mean ${metricName}</td><td>${fmtPct(nom.mean)}</td><td>${fmtPct(real.mean)}</td></tr>
        <tr><td>Median ${metricName}</td><td>${fmtPct(nom.median)}</td><td>${fmtPct(real.median)}</td></tr>
        <tr><td>Best ${metricName}</td><td>${bestCell(nom)}</td><td>${bestCell(real)}</td></tr>
        <tr><td>Worst ${metricName}</td><td>${worstCell(nom)}</td><td>${worstCell(real)}</td></tr>
        <tr><td>Windows with negative ${metricName}</td><td>${negCell(nom)}</td><td>${negCell(real)}</td></tr>
        <tr><td>${fmtDollar(totalInvested)} at oldest window (${firstRow.start})</td><td>${fmtDollar(firstRow.nominal_terminal)}</td><td>${fmtDollar(firstRow.real_terminal)}</td></tr>
        <tr><td>${fmtDollar(totalInvested)} at most recent window (${lastRow.start})</td><td>${fmtDollar(lastRow.nominal_terminal)}</td><td>${fmtDollar(lastRow.real_terminal)}</td></tr>
      </tbody>
    </table>
  `;
}

loadData().catch((err) => {
  const main = document.querySelector('main');
  const banner = document.createElement('article');
  banner.style.background = '#fee';
  banner.innerHTML = `<strong>Error loading data:</strong> ${err.message}<br>
    <small>Did you run <code>python -m src.export</code> to generate <code>docs/data/&lt;slug&gt;.json</code>?</small>`;
  main.insertBefore(banner, main.firstChild);
});
