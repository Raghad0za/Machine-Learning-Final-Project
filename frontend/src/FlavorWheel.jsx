// The flavor wheel, built from our own data: inner ring = 8 flavor families (size = number of coffees),
// outer ring = the most common notes of each family. Clicking a slice runs a live recommendation.
import { useState } from "react";
import { FAMILIES, FAMILY_COLOR, FAMILY_NAME, num, report } from "./data.js";

const C = 200;
const LIGHT_TEXT = new Set(["fruity", "floral", "chocolate", "spice", "tea", "nutty"]);
const SHORT = { caramel_sweet: "كراميل" };
const RING = 54; // room for a radial label, in px

// Split a note label into 1 or 2 lines that fit the ring, or return null (then only hover shows it).
function fitLabel(label, arcPx) {
  const w = (t) => t.length * 5.4;
  if (w(label) <= RING && arcPx >= 12) return [label];
  const words = label.split(" ");
  if (words.length === 2 && arcPx >= 24 && words.every((x) => w(x) <= RING)) return words;
  return null;
}

function polar(r, a) {
  const rad = ((a - 90) * Math.PI) / 180;
  return [C + r * Math.cos(rad), C + r * Math.sin(rad)];
}

function arc(r0, r1, a0, a1) {
  const large = a1 - a0 > 180 ? 1 : 0;
  const [x0, y0] = polar(r1, a0), [x1, y1] = polar(r1, a1);
  const [x2, y2] = polar(r0, a1), [x3, y3] = polar(r0, a0);
  return `M${x0},${y0} A${r1},${r1} 0 ${large} 1 ${x1},${y1} L${x2},${y2} A${r0},${r0} 0 ${large} 0 ${x3},${y3} Z`;
}

export default function FlavorWheel({ onPick }) {
  const [hover, setHover] = useState(null);
  const wheel = report.data.wheel;
  const total = FAMILIES.reduce((s, f) => s + wheel[f].count, 0);
  const gap = 0.6;

  let angle = 0;
  const slices = FAMILIES.map((f, i) => {
    const span = (wheel[f].count / total) * 360;
    const slice = { f, a0: angle, a1: angle + span, i };
    angle += span;
    return slice;
  });

  const center = hover
    ? { big: num(hover.count), small: hover.label }
    : { big: num(report.data.n_coffees), small: "محصول قهوة مختصة" };
  const pick = (choice) => onPick && onPick(choice);

  return (
    <figure className="wheel">
      <svg viewBox="0 0 400 400" role="img" aria-label="عجلة النكهات من بياناتنا">
        {slices.map(({ f, a0, a1, i }) => {
          const notes = wheel[f].notes;
          const famLabel = FAMILY_NAME[f];
          const span = a1 - a0;
          let na = a0;
          const [lx, ly] = polar(103, (a0 + a1) / 2);
          const enter = () => setHover({ f, label: famLabel, count: wheel[f].count });
          return (
            <g key={f} className="wheel-slice" style={{ animationDelay: `${i * 70}ms` }}>
              <path d={arc(70, 136, a0 + gap / 2, a1 - gap / 2)} fill={FAMILY_COLOR[f]}
                    className={hover && hover.f !== f ? "dim" : ""}
                    tabIndex={0} role="button" aria-label={`${famLabel}: ${wheel[f].count}`}
                    onMouseEnter={enter} onMouseLeave={() => setHover(null)} onFocus={enter} onBlur={() => setHover(null)}
                    onClick={() => pick({ family: f })}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && pick({ family: f })} />
              {span > 14 && (
                <text x={lx} y={ly} className={`wheel-fam ${LIGHT_TEXT.has(f) ? "on-dark" : "on-light"}`}
                      textAnchor="middle" dominantBaseline="middle" pointerEvents="none">{SHORT[f] || famLabel}</text>
              )}
              {notes.map(([note, count, noteAr]) => {
                const s = (count / wheel[f].count) * span;
                const b0 = na, b1 = na + s;
                na = b1;
                const mid = (b0 + b1) / 2;
                const [tx, ty] = polar(166, mid);
                const lines = fitLabel(noteAr, (166 * s * Math.PI) / 180);
                const rot = mid <= 180 ? mid - 90 : mid + 90;
                return (
                  <g key={note}>
                    <path d={arc(139, 193, b0 + gap / 2, b1 - gap / 2)} fill={FAMILY_COLOR[f]} fillOpacity="0.4"
                          className={hover && hover.f !== f ? "dim" : ""}
                          onMouseEnter={() => setHover({ f, label: noteAr, count })}
                          onMouseLeave={() => setHover(null)}
                          onClick={() => pick({ family: f, noteAr })} />
                    {lines && (
                      <text x={tx} y={ty} className="wheel-note" textAnchor="middle" dominantBaseline="middle"
                            transform={`rotate(${rot} ${tx} ${ty})`} pointerEvents="none">
                        {lines.length === 1 ? lines[0] : lines.map((ln, k) => (
                          <tspan key={k} x={tx} dy={k === 0 ? "-0.55em" : "1.1em"}>{ln}</tspan>
                        ))}
                      </text>
                    )}
                  </g>
                );
              })}
              {na < a1 - gap && (
                <path d={arc(139, 193, na + gap / 2, a1 - gap / 2)} fill={FAMILY_COLOR[f]} fillOpacity="0.13"
                      className={hover && hover.f !== f ? "dim" : ""} pointerEvents="none" />
              )}
            </g>
          );
        })}
        <circle cx={C} cy={C} r="66" className="wheel-hole" />
        <text x={C} y={C - 4} textAnchor="middle" className="wheel-big">{center.big}</text>
        <text x={C} y={C + 24} textAnchor="middle" className="wheel-small">{center.small}</text>
      </svg>
      <figcaption className="wheel-legend">
        {FAMILIES.map((f) => (
          <button key={f} type="button" className="wheel-key" onClick={() => pick({ family: f })}
                  onMouseEnter={() => setHover({ f, label: FAMILY_NAME[f], count: wheel[f].count })}
                  onMouseLeave={() => setHover(null)}>
            <i style={{ background: FAMILY_COLOR[f] }} />
            {FAMILY_NAME[f]} <span>{num(wheel[f].count)}</span>
          </button>
        ))}
      </figcaption>
    </figure>
  );
}
