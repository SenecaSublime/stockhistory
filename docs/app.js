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

  // Capitalized return-type label, used everywhere so titles/axes read
  // "Nominal CAGR" rather than "nominal CAGR".
  const typeLabel = type === 'nominal' ? 'Nominal' : 'Real';
  const NEG_COLOR = '#cc3333';
  const NEG_FILL = 'rgba(204, 51, 51, 0.18)';

  document.getElementById('cagrHeader').textContent =
    `${horizon}-year rolling ${typeLabel} ${metricName}`;
  document.getElementById('histHeader').textContent =
    `Distribution of ${horizon}-year rolling ${typeLabel} ${metricName}`;
  document.getElementById('terminalHeader').textContent =
    `${typeLabel} terminal value of ${fmtDollar(totalInvested)} contributed over ${horizon} years`;
  document.getElementById('terminalCaption').textContent =
    `${typeLabel} value at the end of the window. Break-even reference: ${fmtDollar(totalInvested)} total contributed. Shaded red where the terminal fell below break-even.`;

  const commonLayout = {
    margin: { t: 20, l: 60, r: 20, b: 50 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
  };
  const config = { responsive: true, displaylogo: false };

  // CAGR/IRR line chart with red fill under zero.
  Plotly.react(
    'cagrChart',
    [
      {
        // Negative-region shading: a trace clamped to min(metric, 0), filled
        // down to y=0. Where metric ≥ 0 both are 0 and nothing fills.
        x,
        y: metric.map((v) => Math.min(v, 0)),
        fill: 'tozeroy',
        fillcolor: NEG_FILL,
        line: { width: 0 },
        mode: 'lines',
        hoverinfo: 'skip',
        showlegend: false,
      },
      {
        x,
        y: metric,
        mode: 'lines',
        name: `${typeLabel} ${metricName}`,
        line: { width: 1.5 },
        hovertemplate: `Start: %{x}<br>${typeLabel} ${metricName}: %{y:.2%}<extra></extra>`,
      },
      {
        // Red markers where metric < 0, on top of the line.
        x: x.filter((_, i) => metric[i] < 0),
        y: metric.filter((v) => v < 0),
        mode: 'markers',
        marker: { color: NEG_COLOR, size: 5 },
        name: 'Negative window',
        hovertemplate: `Start: %{x}<br>${typeLabel} ${metricName}: %{y:.2%}<extra></extra>`,
      },
    ],
    {
      ...commonLayout,
      yaxis: {
        tickformat: '.0%',
        title: { text: `${typeLabel} annualized return (${metricName})` },
        zeroline: true,
      },
      xaxis: { title: { text: 'Window start date' } },
      showlegend: true,
    },
    config
  );

  // Histogram with red bars for negative bins. Manual binning so each bar's
  // color reflects whether its bin's left edge is negative.
  const negCount = metric.filter((v) => v < 0).length;
  const histTraces = buildHistogramTraces(metric, 40, NEG_COLOR);
  Plotly.react(
    'histChart',
    histTraces,
    {
      ...commonLayout,
      xaxis: { tickformat: '.0%', title: { text: `${typeLabel} annualized return (${metricName})` } },
      yaxis: { title: { text: 'Number of windows' } },
      barmode: 'stack',
      showlegend: false,
      annotations: negCount > 0 ? [{
        x: 0, xref: 'x', yref: 'paper', y: 1.0, yanchor: 'bottom', showarrow: false,
        text: `← ${negCount} window${negCount === 1 ? '' : 's'} with negative ${typeLabel.toLowerCase()} ${metricName.toLowerCase()}`,
        font: { color: NEG_COLOR, size: 11 },
      }] : [],
    },
    config
  );

  // Terminal-value line chart with red shading where terminal < total invested.
  Plotly.react(
    'terminalChart',
    [
      {
        // Break-even reference line (drawn first so the red fill goes between
        // it and the terminal-clamped trace).
        x,
        y: x.map(() => totalInvested),
        mode: 'lines',
        line: { width: 1, dash: 'dash', color: 'rgba(0,0,0,0.5)' },
        name: `Break-even (${fmtDollar(totalInvested)})`,
        hoverinfo: 'skip',
      },
      {
        // Clamped to ≤ break-even; with fill='tonexty' the gap to the
        // break-even trace above is shaded red. Where terminal ≥ break-even
        // both are equal to break-even and nothing fills.
        x,
        y: terminal.map((v) => Math.min(v, totalInvested)),
        fill: 'tonexty',
        fillcolor: NEG_FILL,
        line: { width: 0 },
        mode: 'lines',
        hoverinfo: 'skip',
        showlegend: false,
      },
      {
        x,
        y: terminal,
        mode: 'lines',
        name: `${typeLabel} terminal`,
        line: { width: 1.5 },
        hovertemplate: `Start: %{x}<br>${typeLabel} terminal: $%{y:,.0f}<extra></extra>`,
      },
      {
        // Red markers below break-even.
        x: x.filter((_, i) => terminal[i] < totalInvested),
        y: terminal.filter((v) => v < totalInvested),
        mode: 'markers',
        marker: { color: NEG_COLOR, size: 5 },
        name: 'Below break-even',
        hovertemplate: `Start: %{x}<br>${typeLabel} terminal: $%{y:,.0f}<extra></extra>`,
      },
    ],
    {
      ...commonLayout,
      yaxis: { title: { text: `${typeLabel} terminal value ($)` }, tickformat: '$,.0f' },
      xaxis: { title: { text: 'Window start date' } },
      showlegend: true,
    },
    config
  );

  renderStats(rows, horizon, metricName, totalInvested);
}

function buildHistogramTraces(values, nbins, negColor) {
  // Build two stacked-bar traces sharing the same bin grid: one for negative
  // bins (red), one for non-negative (default blue). Stacking with disjoint
  // data renders side-by-side cleanly.
  if (values.length === 0) return [];
  let minV = Math.min(...values);
  let maxV = Math.max(...values);
  if (minV === maxV) { minV -= 0.01; maxV += 0.01; }
  const binWidth = (maxV - minV) / nbins;
  const negY = new Array(nbins).fill(0);
  const posY = new Array(nbins).fill(0);
  for (const v of values) {
    let idx = Math.floor((v - minV) / binWidth);
    if (idx >= nbins) idx = nbins - 1;
    if (idx < 0) idx = 0;
    const center = minV + (idx + 0.5) * binWidth;
    if (center < 0) negY[idx] += 1; else posY[idx] += 1;
  }
  const centers = new Array(nbins).fill(0).map((_, i) => minV + (i + 0.5) * binWidth);
  return [
    {
      x: centers, y: negY, type: 'bar', width: binWidth,
      marker: { color: negColor },
      hovertemplate: 'Bin center: %{x:.1%}<br>Count: %{y}<extra></extra>',
      name: 'Negative',
    },
    {
      x: centers, y: posY, type: 'bar', width: binWidth,
      marker: { color: '#1f77b4' },
      hovertemplate: 'Bin center: %{x:.1%}<br>Count: %{y}<extra></extra>',
      name: 'Non-negative',
    },
  ];
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

  // Helpers that wrap a value cell in a .negative class when it falls below
  // the corresponding threshold (0 for metric values, total_invested for
  // terminal dollars). The class adds red+bold styling via style.css.
  const pctCell = (v) =>
    `<td class="${v < 0 ? 'negative' : ''}">${fmtPct(v)}</td>`;
  const dollarCell = (v) =>
    `<td class="${v < totalInvested ? 'negative' : ''}">${fmtDollar(v)}</td>`;
  const countCell = (s) => {
    const text = `${s.negCount} (${((s.negCount / s.n) * 100).toFixed(1)}%)`;
    return `<td class="${s.negCount > 0 ? 'negative' : ''}">${text}</td>`;
  };
  const bestCell = (s) =>
    `<td class="${s.max < 0 ? 'negative' : ''}">${fmtPct(s.max)}<br><small>${rows[s.maxIdx].start} → ${rows[s.maxIdx].end}</small></td>`;
  const worstCell = (s) =>
    `<td class="${s.min < 0 ? 'negative' : ''}">${fmtPct(s.min)}<br><small>${rows[s.minIdx].start} → ${rows[s.minIdx].end}</small></td>`;

  document.getElementById('stats').innerHTML = `
    <table>
      <thead>
        <tr><th>${horizon}-year windows</th><th>Nominal</th><th>Real</th></tr>
      </thead>
      <tbody>
        <tr><td>Number of windows</td><td>${nom.n.toLocaleString()}</td><td>${real.n.toLocaleString()}</td></tr>
        <tr><td>Mean ${metricName}</td>${pctCell(nom.mean)}${pctCell(real.mean)}</tr>
        <tr><td>Median ${metricName}</td>${pctCell(nom.median)}${pctCell(real.median)}</tr>
        <tr><td>Best ${metricName}</td>${bestCell(nom)}${bestCell(real)}</tr>
        <tr><td>Worst ${metricName}</td>${worstCell(nom)}${worstCell(real)}</tr>
        <tr><td>Windows with negative ${metricName}</td>${countCell(nom)}${countCell(real)}</tr>
        <tr><td>${fmtDollar(totalInvested)} at oldest window (${firstRow.start})</td>${dollarCell(firstRow.nominal_terminal)}${dollarCell(firstRow.real_terminal)}</tr>
        <tr><td>${fmtDollar(totalInvested)} at most recent window (${lastRow.start})</td>${dollarCell(lastRow.nominal_terminal)}${dollarCell(lastRow.real_terminal)}</tr>
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
