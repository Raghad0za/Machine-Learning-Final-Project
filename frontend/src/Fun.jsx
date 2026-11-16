// Small playful pieces used by the slides and the demo.
import { useEffect, useState } from "react";
import { FAMILIES, FAMILY_COLOR, FAMILY_NAME, num } from "./data.js";

const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// A number that counts from `from` to `to` when it appears.
export function CountUp({ from = 0, to, duration = 1200, format = num, delay = 0 }) {
  const [v, setV] = useState(reduceMotion() ? to : from);
  useEffect(() => {
    if (reduceMotion()) { setV(to); return undefined; }
    let raf, start;
    const timer = setTimeout(() => {
      const step = (t) => {
        start = start ?? t;
        const k = Math.min(1, (t - start) / duration);
        const eased = 1 - Math.pow(1 - k, 3);
        setV(from + (to - from) * eased);
        if (k < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }, delay);
    return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
  }, [from, to, duration, delay]);
  return <>{format(Math.round(v))}</>;
}

// Ring showing one share (0..1), with the value in the middle.
export function Ring({ value, color = "var(--sage)", size = 120, label }) {
  const r = 42, c = 2 * Math.PI * r;
  return (
    <figure className="ring" style={{ width: size }}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={r} className="ring-track" />
        <circle cx="50" cy="50" r={r} className="ring-fill" stroke={color}
                strokeDasharray={`${c * value} ${c}`} transform="rotate(-90 50 50)" />
      </svg>
      <b>{Math.round(value * 100)}٪</b>
      {label && <figcaption>{label}</figcaption>}
    </figure>
  );
}

// Tiny donut of flavor families (used for the personality cards).
export function FlavorDonut({ shares, size = 64 }) {
  const items = FAMILIES.map((f) => ({ f, v: Math.max(0, shares[f] || 0) })).filter((x) => x.v > 0.04);
  const total = items.reduce((s, x) => s + x.v, 0) || 1;
  const r = 15.9, c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg className="donut" viewBox="0 0 40 40" width={size} height={size} role="img"
         aria-label={items.map((x) => FAMILY_NAME[x.f]).join("، ")}>
      {items.map((x) => {
        const len = (x.v / total) * c;
        const el = <circle key={x.f} cx="20" cy="20" r={r} fill="none" stroke={FAMILY_COLOR[x.f]} strokeWidth="7"
                           strokeDasharray={`${Math.max(0, len - 0.8)} ${c}`} strokeDashoffset={-offset} transform="rotate(-90 20 20)" />;
        offset += len;
        return el;
      })}
    </svg>
  );
}

// A thin ribbon of the coffee's flavor families (top of every result card).
export function FlavorRibbon({ families }) {
  const list = families && families.length ? families : [];
  return (
    <div className="ribbon" aria-label={list.map((f) => FAMILY_NAME[f]).join("، ")}>
      {list.map((f) => <i key={f} style={{ background: FAMILY_COLOR[f] }} title={FAMILY_NAME[f]} />)}
    </div>
  );
}

// Card that flips to show its back side.
export function FlipCard({ front, back, tone = "sup" }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <button type="button" className={`flip ${flipped ? "flipped" : ""} tone-${tone}`} onClick={() => setFlipped(!flipped)}
            aria-pressed={flipped}>
      <span className="flip-inner">
        <span className="flip-face flip-front">{front}</span>
        <span className="flip-face flip-back">{back}</span>
      </span>
    </button>
  );
}

// Messy spellings that collapse into one clean value when you press the button.
const SPOTS = [[30, 12, -8], [68, 18, 6], [42, 34, 3], [70, 44, -5], [28, 56, 7], [55, 64, -3], [72, 80, 9],
               [32, 86, -6], [50, 48, 4], [62, 30, -9], [38, 72, 10], [66, 62, -4]];

export function MessyChips({ groups, cleanLabel, messyLabel }) {
  const [clean, setClean] = useState(false);
  return (
    <div className="messy-wrap">
      <div className={`messy ${clean ? "is-clean" : ""}`}>
        {groups.map((g, gi) => (
          <div className="messy-group" key={g.clean}>
            {g.items.map((x, i) => {
              const [l, t, rot] = SPOTS[(i + gi * 5) % SPOTS.length];
              return (
                <span key={x} className="messy-chip"
                      style={{ "--l": `${l}%`, "--t": `${t}%`, "--rot": `${rot}deg`, transitionDelay: `${i * 40}ms` }}>{x}</span>
              );
            })}
            <span className="messy-final" style={{ "--c": g.color }}>{g.clean}</span>
          </div>
        ))}
      </div>
      <button type="button" className={clean ? "secondary" : "primary"} onClick={() => setClean(!clean)}>
        {clean ? messyLabel : cleanLabel}
      </button>
    </div>
  );
}

// Line icons (stroke uses currentColor).
const PATHS = {
  chat: "M5 6h22a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H14l-6 5v-5H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zM10 13h12M10 17h8",
  heart: "M16 27s-10-6-10-13a5.5 5.5 0 0 1 10-3 5.5 5.5 0 0 1 10 3c0 7-10 13-10 13z",
  cards: "M7 9h12v16H7zM13 6h12v16",
  read: "M4 16s5-8 12-8 12 8 12 8-5 8-12 8S4 16 4 16zM16 12a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  funnel: "M4 6h24l-9 11v8l-6 3V17z",
  scale: "M16 5v22M8 27h16M6 10h20M6 10l-3 8h6zM26 10l-3 8h6z",
  star: "M16 4l3.5 7.5 8 1-6 5.5 1.5 8L16 22l-7 4 1.5-8-6-5.5 8-1z",
  screen: "M4 6h24v16H4zM12 27h8M16 22v5",
  server: "M6 5h20v9H6zM6 18h20v9H6zM10 9.5h2M10 22.5h2",
  gear: "M16 11a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM16 3v4M16 25v4M3 16h4M25 16h4M7 7l3 3M22 22l3 3M25 7l-3 3M10 22l-3 3",
  table: "M5 6h22v20H5zM5 12h22M5 19h22M14 6v20",
  book: "M6 5h9a3 3 0 0 1 3 3v19a2 2 0 0 0-2-2H6zM26 5h-5a3 3 0 0 0-3 3",
  thumbs: "M10 14l5-9a3 3 0 0 1 3 3v5h7a2 2 0 0 1 2 2.3l-2 9A2 2 0 0 1 23 26H10zM4 14h6v12H4z",
  drop: "M16 4s-9 10-9 16a9 9 0 0 0 18 0c0-6-9-16-9-16z",
  words: "M5 8h10M10 8v14M19 14h8M23 14v8M5 26h22",
  tag: "M4 16V5h11l13 13-11 11zM10 10h.01",
  phone: "M10 3h12v26H10zM15 25h2",
  target: "M16 4a12 12 0 1 0 0 24 12 12 0 0 0 0-24zM16 10a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM16 15.5v1",
  play: "M10 6l16 10-16 10z",
  dots: "M6 16h.01M16 16h.01M26 16h.01M11 8h.01M21 8h.01M11 24h.01M21 24h.01",
};

export function Icon({ name, size = 28 }) {
  return (
    <svg className="icon" viewBox="0 0 32 32" width={size} height={size} aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
