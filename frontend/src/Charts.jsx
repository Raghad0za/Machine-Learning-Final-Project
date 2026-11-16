// Small hand-made charts (HTML/SVG). Values are always written next to the marks,
// so color is never the only way to read them. Hover (or tap) shows the details.
import { useState } from "react";

export function useTip() {
  const [tip, setTip] = useState(null);
  const bind = (content) => ({
    onMouseMove: (e) => setTip({ x: e.clientX, y: e.clientY, content }),
    onMouseLeave: () => setTip(null),
    onClick: (e) => setTip({ x: e.clientX, y: e.clientY, content }),
  });
  const node = tip ? (
    <div className="tip" role="status" style={{ left: tip.x, top: tip.y }}>{tip.content}</div>
  ) : null;
  return [bind, node];
}

// Horizontal bars, one series. rows: [{label, value, color?, note?}]
export function BarList({ rows, color, format = (v) => v, max, unit = "", refLine, refLabel }) {
  const [bind, tip] = useTip();
  const top = max ?? Math.max(...rows.map((r) => r.value));
  return (
    <div className="barlist">
      {rows.map((r) => (
        <div className="barlist-row" key={r.label} {...bind(<><b>{r.label}</b> {format(r.value)}{unit}{r.note ? <>, {r.note}</> : null}</>)}>
          <span className="barlist-label">{r.label}</span>
          <span className="barlist-track">
            <span className="barlist-bar" style={{ width: `${(r.value / top) * 100}%`, background: r.color || color }} />
            {refLine != null && <span className="barlist-ref" style={{ insetInlineStart: `${(refLine / top) * 100}%` }} />}
          </span>
          <span className="barlist-value">{format(r.value)}{unit}</span>
        </div>
      ))}
      {refLabel && <div className="barlist-reflabel">{refLabel}</div>}
      {tip}
    </div>
  );
}

// Vertical grouped bars. groups: [label], series: [{name, color, values:[]}]
export function GroupedBars({ groups, series, format = (v) => v, max = 1, height = 220 }) {
  const [bind, tip] = useTip();
  return (
    <div className="grouped">
      <div className="legend">
        {series.map((s) => (
          <span key={s.name} className="legend-item"><i style={{ background: s.color }} />{s.name}</span>
        ))}
      </div>
      <div className="grouped-plot" style={{ height }}>
        {groups.map((g, gi) => (
          <div className="grouped-group" key={g}>
            <div className="grouped-bars">
              {series.map((s) => (
                <div className="grouped-col" key={s.name} {...bind(<><b>{g}</b><br />{s.name}: {format(s.values[gi])}</>)}>
                  <span className="grouped-value">{format(s.values[gi])}</span>
                  <span className="grouped-bar" style={{ height: `${(s.values[gi] / max) * 100}%`, background: s.color }} />
                </div>
              ))}
            </div>
            <div className="grouped-label">{g}</div>
          </div>
        ))}
      </div>
      {tip}
    </div>
  );
}

// Histogram with a median marker. bins = counts for equal-width bins between lo and hi.
export function Histogram({ bins, lo, hi, median, color, medianLabel, axisLabel }) {
  const [bind, tip] = useTip();
  const top = Math.max(...bins);
  const width = (hi - lo) / bins.length;
  return (
    <div className="histo">
      <div className="histo-plot">
        {bins.map((b, i) => {
          const from = lo + i * width;
          const to = from + width;
          const label = i === bins.length - 1 ? `${from}+` : `${from}-${to}`;
          return (
            <div className="histo-col" key={i} {...bind(<><b>{label} ريال</b><br />{b} محصول</>)}>
              <span className="histo-bar" style={{ height: `${(b / top) * 100}%`, background: color }} />
            </div>
          );
        })}
        <div className="histo-median" style={{ insetInlineStart: `${((median - lo) / (hi - lo)) * 100}%` }}>
          <span>{medianLabel}</span>
        </div>
      </div>
      <div className="histo-axis">
        <span>{lo}</span><span>{(lo + hi) / 2}</span><span>{hi}+</span>
      </div>
      <div className="axis-title">{axisLabel}</div>
      {tip}
    </div>
  );
}

// Small line chart (silhouette by k). Always left to right, numbers are not mirrored.
export function LineChart({ points, highlight, color, yLabel }) {
  const [bind, tip] = useTip();
  const w = 320, h = 150, pad = 28;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys) - 0.03, y1 = Math.max(...ys) + 0.03;
  const sx = (x) => pad + ((x - x0) / (x1 - x0)) * (w - pad * 1.5);
  const sy = (y) => h - pad - ((y - y0) / (y1 - y0)) * (h - pad * 1.6);
  const d = points.map((p, i) => `${i ? "L" : "M"}${sx(p.x)},${sy(p.y)}`).join(" ");
  return (
    <div className="linechart" dir="ltr">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={yLabel}>
        <line x1={pad} x2={w - pad / 2} y1={h - pad} y2={h - pad} className="axis" />
        <path d={d} fill="none" stroke={color} strokeWidth="2" />
        {points.map((p) => (
          <g key={p.x} {...bind(<><b>{p.x} مجموعات</b><br />{yLabel}: {p.y.toFixed(3)}</>)}>
            <circle cx={sx(p.x)} cy={sy(p.y)} r="12" fill="transparent" />
            <circle cx={sx(p.x)} cy={sy(p.y)} r={p.x === highlight ? 6 : 4} fill={p.x === highlight ? color : "var(--surface)"} stroke={color} strokeWidth="2" />
            <text x={sx(p.x)} y={h - pad + 16} textAnchor="middle" className="tick">{p.x}</text>
            {p.x === highlight && <text x={sx(p.x)} y={sy(p.y) - 12} textAnchor="middle" className="value">{p.y.toFixed(2)}</text>}
          </g>
        ))}
      </svg>
      {tip}
    </div>
  );
}
