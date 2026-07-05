"""
Regenerate the interactive BTC halving-cycle chart from a fresh price CSV.

USAGE:
    python regenerate_chart.py prices.csv output_chart.html

INPUT CSV FORMAT (two columns, header required):
    date,price
    2013-06-24,107.98
    2013-06-25,102.98
    ...
    (daily granularity; any parseable date format works)

WHAT THIS DOES:
    1. Loads the price series.
    2. For each halving cycle window [halving_i, halving_{i+1}), finds the
       "significant peak" -- the local ATH preceding the deepest subsequent
       drawdown before a new ATH is made -- and its paired trough.
    3. Rebuilds the full interactive HTML (same layout/style as before) with
       the recomputed peaks, troughs, and drawdown bands.

To add a new halving once it actually happens, edit the HALVINGS list below.
"""

import sys
import json
import pandas as pd

# ---- Known halving dates. Add new ones here as they occur. ----
HALVINGS = [
    "2016-07-09",
    "2020-05-11",
    "2024-04-20",
]
NEXT_HALVING_ESTIMATE = "2028-04-17"  # rough ~4yr cadence guess; update when block-time data narrows it down


def find_significant_peak(window_series, full_series):
    cummax = window_series.cummax()
    candidates = window_series[window_series == cummax]
    best = None
    for t, p in candidates.items():
        future = full_series.loc[t:]
        exceed = future[future > p]
        if len(exceed) > 0:
            end = exceed.index[0]
            trough_win = full_series.loc[t:end]
            complete = True
        else:
            trough_win = full_series.loc[t:]
            end = None
            complete = False
        trough_date = trough_win.idxmin()
        trough_price = trough_win.loc[trough_date]
        dd = (trough_price - p) / p * 100
        if best is None or dd < best["dd"]:
            best = dict(peak_date=t, peak_price=p, trough_date=trough_date,
                        trough_price=trough_price, dd=dd, new_ath_date=end, complete=complete)
    return best


def compute_cycles(price: pd.Series, halving_dates):
    halvings = pd.to_datetime(halving_dates)
    data_end = price.index.max()
    results = []
    for i, h in enumerate(halvings):
        window_end = halvings[i + 1] if i + 1 < len(halvings) else data_end
        window = price.loc[h:window_end]
        if window.empty:
            continue
        best = find_significant_peak(window, price)
        results.append({
            "cycle": i + 2,  # cycle numbering starts at 2 (first halving with full pre-history is #1, excluded)
            "halving_date": h,
            "peak_date": best["peak_date"],
            "peak_price": best["peak_price"],
            "days_to_peak": (best["peak_date"] - h).days,
            "trough_date": best["trough_date"],
            "trough_price": best["trough_price"],
            "drawdown_pct": best["dd"],
            "cycle_complete": best["complete"],
        })
    return pd.DataFrame(results)


def build_payload(price: pd.Series, res: pd.DataFrame, halving_dates):
    payload = {
        "dates": [d.strftime("%Y-%m-%d") for d in price.index],
        "prices": [round(float(p), 2) for p in price.values],
        "halvings": [{"date": h, "label": f"Halving #{i+2}"} for i, h in enumerate(halving_dates)]
                    + [{"date": NEXT_HALVING_ESTIMATE, "label": "Next halving (est.)", "projected": True}],
        "peaks": [],
        "troughs": [],
    }
    for _, r in res.iterrows():
        c = int(r["cycle"])
        payload["peaks"].append({
            "date": r["peak_date"].strftime("%Y-%m-%d"),
            "price": round(float(r["peak_price"]), 2),
            "cycle": c,
            "days_to_peak": int(r["days_to_peak"]),
            "text": f"Cycle {c} peak: ${r['peak_price']:,.0f}<br>{int(r['days_to_peak'])} days post-halving",
        })
        payload["troughs"].append({
            "date": r["trough_date"].strftime("%Y-%m-%d"),
            "price": round(float(r["trough_price"]), 2),
            "cycle": c,
            "drawdown_pct": round(float(r["drawdown_pct"]), 1),
            "complete": bool(r["cycle_complete"]),
            "text": f"Cycle {c} trough: ${r['trough_price']:,.0f}<br>{r['drawdown_pct']:.1f}% from peak"
                    + ("" if r["cycle_complete"] else " (ongoing)"),
        })
    return payload


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Bitcoin Halving Cycles - Interactive</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.32.0/plotly.min.js"></script>
<style>
  html, body {{ margin: 0; padding: 0; background: #0f1117; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e6e6e6; }}
  #header {{ padding: 18px 24px 6px 24px; }}
  #header h1 {{ font-size: 19px; margin: 0 0 4px 0; font-weight: 700; color: #f5f5f5; }}
  #header p {{ font-size: 12px; margin: 0; color: #9aa0ab; line-height: 1.5; }}
  #legend-note {{ font-size: 11.5px; color: #777c88; padding: 0 24px 10px 24px; }}
  #chart {{ width: 100%; height: 640px; }}
  #stats {{ padding: 6px 24px 22px 24px; display: flex; gap: 14px; flex-wrap: wrap; }}
  .card {{ background: #171a22; border: 1px solid #2a2f3a; border-radius: 8px; padding: 10px 14px; min-width: 200px; flex: 1; }}
  .card h3 {{ margin: 0 0 6px 0; font-size: 12.5px; color: #f2a900; }}
  .card table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; }}
  .card td {{ padding: 2px 4px; color: #cfd3da; }}
  .card td.label {{ color: #8a8f99; }}
  .badge {{ display:inline-block; padding:1px 6px; border-radius: 10px; font-size: 10px; font-weight:700; }}
  .badge.done {{ background:#1e3a2a; color:#3ddc84; }}
  .badge.live {{ background:#3a2a1e; color:#ffb454; }}
</style>
</head>
<body>

<div id="header">
  <h1>Bitcoin Halving Cycles — Interactive</h1>
  <p>Drag the range slider or scroll/zoom on the chart to pan through history. Click legend items to toggle series.
     Vertical dashed lines mark halvings. Shaded bands mark each cycle's peak-to-trough drawdown window.
     Peaks use the "significant peak" method (local ATH preceding the deepest subsequent drawdown before a new ATH is made).</p>
</div>

<div id="chart"></div>
<div id="stats"></div>

<script>
const DATA = {payload_json};

const priceTrace = {{
  x: DATA.dates, y: DATA.prices, type: 'scatter', mode: 'lines', name: 'BTC / USD',
  line: {{ color: '#f2a900', width: 1.4 }},
  hovertemplate: '%{{x}}<br>$%{{y:,.0f}}<extra></extra>'
}};

function markerTrace(arr, name, symbol, color, size) {{
  return {{
    x: arr.map(d => d.date), y: arr.map(d => d.price), type: 'scatter', mode: 'markers', name: name,
    marker: {{ symbol: symbol, size: size, color: color, line: {{ color: '#fff', width: 1 }} }},
    text: arr.map(d => d.text), hovertemplate: '%{{text}}<extra></extra>'
  }};
}}

const peakTrace = markerTrace(DATA.peaks, 'Cycle Peak', 'triangle-up', '#3ddc84', 14);
const troughTrace = markerTrace(DATA.troughs, 'Cycle Trough', 'triangle-down', '#ff5c5c', 14);
const traces = [priceTrace, peakTrace, troughTrace];

const halvingShapes = DATA.halvings.map(h => ({{
  type: 'line', x0: h.date, x1: h.date, y0: 0, y1: 1, xref: 'x', yref: 'paper',
  line: {{ color: '#5b8def', width: 1.3, dash: h.projected ? 'dot' : 'dash' }},
  opacity: h.projected ? 0.5 : 0.85
}}));

const drawdownShapes = DATA.peaks.map((p, i) => {{
  const t = DATA.troughs[i];
  return {{
    type: 'rect', x0: p.date, x1: t.date, y0: 0, y1: 1, xref: 'x', yref: 'paper',
    fillcolor: t.complete ? 'rgba(255,92,92,0.10)' : 'rgba(255,180,84,0.10)',
    line: {{ width: 0 }}, layer: 'below'
  }};
}});

const shapes = halvingShapes.concat(drawdownShapes);

const annotations = DATA.halvings.map(h => ({{
  x: h.date, y: 1.0, xref: 'x', yref: 'paper', text: h.label, showarrow: false,
  textangle: -90, xanchor: 'right', yanchor: 'top',
  font: {{ size: 10, color: '#5b8def' }}, opacity: h.projected ? 0.65 : 1
}})).concat(DATA.peaks.map((p, i) => {{
  const t = DATA.troughs[i];
  return {{
    x: p.date, y: 1.0, xref: 'x', yref: 'paper',
    text: `Cycle ${{p.cycle}} drawdown: ${{t.drawdown_pct}}%${{t.complete ? '' : ' (ongoing)'}}`,
    showarrow: false, xanchor: 'left', yanchor: 'bottom',
    font: {{ size: 9.5, color: t.complete ? '#ff8080' : '#ffb454' }}, opacity: 0.9
  }};
}}));

const layout = {{
  paper_bgcolor: '#0f1117', plot_bgcolor: '#0f1117', font: {{ color: '#c9ccd3', size: 11 }},
  margin: {{ l: 70, r: 30, t: 34, b: 10 }}, showlegend: true,
  legend: {{ orientation: 'h', y: -0.15, x: 0.5, xanchor: 'center', bgcolor: 'rgba(0,0,0,0)', font: {{ size: 10.5 }} }},
  hovermode: 'closest',
  xaxis: {{
    type: 'date', gridcolor: '#1e222c',
    rangeslider: {{ visible: true, bgcolor: '#171a22', bordercolor: '#2a2f3a', thickness: 0.09 }},
    rangeselector: {{
      bgcolor: '#171a22', activecolor: '#f2a900', bordercolor: '#2a2f3a', font: {{ color: '#e6e6e6', size: 10.5 }},
      buttons: [
        {{ count: 6, label: '6m', step: 'month', stepmode: 'backward' }},
        {{ count: 1, label: '1y', step: 'year', stepmode: 'backward' }},
        {{ count: 2, label: '2y', step: 'year', stepmode: 'backward' }},
        {{ count: 4, label: '4y', step: 'year', stepmode: 'backward' }},
        {{ step: 'all', label: 'All' }}
      ]
    }},
  }},
  yaxis: {{ type: 'log', title: 'BTC / USD (log scale)', gridcolor: '#1e222c', tickprefix: '$', tickformat: ',.0f' }},
  shapes: shapes, annotations: annotations,
}};

Plotly.newPlot('chart', traces, layout, {{ responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }});

const statsDiv = document.getElementById('stats');
DATA.peaks.forEach((p, i) => {{
  const t = DATA.troughs[i];
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <h3>Cycle ${{p.cycle}} <span class="badge ${{t.complete ? 'done' : 'live'}}">${{t.complete ? 'Completed' : 'In progress'}}</span></h3>
    <table>
      <tr><td class="label">Peak</td><td>$${{p.price.toLocaleString()}} (${{p.date}})</td></tr>
      <tr><td class="label">Days to peak</td><td>${{p.days_to_peak}}d post-halving</td></tr>
      <tr><td class="label">Trough</td><td>$${{t.price.toLocaleString()}} (${{t.date}})</td></tr>
      <tr><td class="label">Drawdown</td><td>${{t.drawdown_pct}}%</td></tr>
    </table>`;
  statsDiv.appendChild(card);
}});
</script>

<div id="legend-note">
  Data: CoinStats daily BTC/USD, {date_start} to {date_end}. Next-halving date is a rough estimate and will shift based on actual block-time
  drift. Shaded bands span each cycle's peak to its trough (red = completed cycle, orange = still in progress).
</div>

</body>
</html>
"""


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    csv_path, out_path = sys.argv[1], sys.argv[2]

    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    price = df["price"].resample("D").last().dropna()

    res = compute_cycles(price, HALVINGS)
    payload = build_payload(price, res, HALVINGS)

    html = HTML_TEMPLATE.format(
        payload_json=json.dumps(payload),
        date_start=price.index.min().strftime("%Y-%m-%d"),
        date_end=price.index.max().strftime("%Y-%m-%d"),
    )

    with open(out_path, "w") as f:
        f.write(html)

    print(f"Wrote {out_path} ({len(price)} price points, {len(res)} cycles detected)")
    print(res[["cycle", "halving_date", "peak_date", "peak_price", "trough_date", "trough_price", "drawdown_pct", "cycle_complete"]])


if __name__ == "__main__":
    main()
