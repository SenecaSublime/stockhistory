let DATA = null;

const fmtPct = (x) => `${(x * 100).toFixed(2)}%`;
const fmtDollar = (x) => `$${x.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

async function loadData() {
  const resp = await fetch('data/returns.json');
  if (!resp.ok) throw new Error(`Failed to load returns.json: ${resp.status}`);
  DATA = await resp.json();
  render();
}

function selected() {
  return {
    horizon: document.getElementById('horizon').value,
    type: document.getElementById('returnType').value,
  };
}

function render() {
  const { horizon, type } = selected();
  const rows = DATA.rolling[horizon];
  if (!rows || rows.length === 0) return;

  const cagrKey = `${type}_cagr`;
  const termKey = `${type}_terminal`;

  const x = rows.map(r => r.start);
  const cagr = rows.map(r => r[cagrKey]);
  const terminal = rows.map(r => r[termKey] * 1000);

  const commonLayout = {
    margin: { t: 20, l: 60, r: 20, b: 50 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
  };
  const config = { responsive: true, displaylogo: false };

  Plotly.react('cagrChart', [{
    x, y: cagr, mode: 'lines', name: 'CAGR',
    line: { width: 1.5 },
    hovertemplate: 'Start: %{x}<br>CAGR: %{y:.2%}<extra></extra>',
  }], {
    ...commonLayout,
    yaxis: { tickformat: '.0%', title: { text: 'Annualized return' }, zeroline: true },
    xaxis: { title: { text: 'Window start date' } },
  }, config);

  Plotly.react('histChart', [{
    x: cagr, type: 'histogram', nbinsx: 40,
    hovertemplate: 'Bin: %{x:.1%}<br>Count: %{y}<extra></extra>',
  }], {
    ...commonLayout,
    xaxis: { tickformat: '.0%', title: { text: 'Annualized return' } },
    yaxis: { title: { text: 'Number of windows' } },
  }, config);

  Plotly.react('terminalChart', [{
    x, y: terminal, mode: 'lines',
    line: { width: 1.5 },
    hovertemplate: 'Start: %{x}<br>Terminal: $%{y:,.0f}<extra></extra>',
  }], {
    ...commonLayout,
    yaxis: { title: { text: 'Terminal value ($)' }, tickformat: '$,.0f' },
    xaxis: { title: { text: 'Window start date' } },
  }, config);

  renderStats(rows, cagr, terminal, horizon, type);
}

function renderStats(rows, cagr, terminal, horizon, type) {
  const n = cagr.length;
  const mean = cagr.reduce((a, b) => a + b, 0) / n;
  const sorted = [...cagr].sort((a, b) => a - b);
  const median = sorted[Math.floor(n / 2)];
  const min = sorted[0];
  const max = sorted[n - 1];
  const minIdx = cagr.indexOf(min);
  const maxIdx = cagr.indexOf(max);
  const negCount = cagr.filter(c => c < 0).length;
  const finalTerm = terminal[terminal.length - 1];
  const firstTerm = terminal[0];

  document.getElementById('stats').innerHTML = `
    <table>
      <thead>
        <tr><th>${horizon}-year ${type} windows</th><th>Value</th></tr>
      </thead>
      <tbody>
        <tr><td>Number of windows</td><td>${n.toLocaleString()}</td></tr>
        <tr><td>Mean CAGR</td><td>${fmtPct(mean)}</td></tr>
        <tr><td>Median CAGR</td><td>${fmtPct(median)}</td></tr>
        <tr><td>Best window</td><td>${fmtPct(max)} (start ${rows[maxIdx].start} → end ${rows[maxIdx].end})</td></tr>
        <tr><td>Worst window</td><td>${fmtPct(min)} (start ${rows[minIdx].start} → end ${rows[minIdx].end})</td></tr>
        <tr><td>Windows with negative CAGR</td><td>${negCount} (${((negCount / n) * 100).toFixed(1)}%)</td></tr>
        <tr><td>$1,000 starting at oldest window</td><td>${fmtDollar(firstTerm)}</td></tr>
        <tr><td>$1,000 starting at most recent complete window</td><td>${fmtDollar(finalTerm)}</td></tr>
      </tbody>
    </table>
  `;
}

document.getElementById('horizon').addEventListener('change', render);
document.getElementById('returnType').addEventListener('change', render);

loadData().catch(err => {
  const main = document.querySelector('main');
  const banner = document.createElement('article');
  banner.style.background = '#fee';
  banner.innerHTML = `<strong>Error loading data:</strong> ${err.message}<br>
    <small>Did you run <code>python -m src.export</code> to generate <code>docs/data/returns.json</code>?</small>`;
  main.insertBefore(banner, main.firstChild);
});
