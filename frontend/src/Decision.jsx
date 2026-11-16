// "How it decided": the KNN steps, drawn from the `explain` part of the API answer.
// 1) the sentence becomes a point   2) the filters   3) the distance of every coffee   4) why #1 won
import { useEffect, useMemo, useState } from "react";
import { FAMILY_COLOR, FAMILY_NAME, PROFILE_COLOR, ar, num, profiles } from "./data.js";
import { Icon } from "./Fun.jsx";

export const BLOCKS = {
  notes: { label: "النكهات", color: "#C25B5B" },
  families: { label: "عائلة النكهة", color: "#C9A227" },
  body: { label: "القوام", color: "#8F4522" },
  acidity: { label: "الحموضة", color: "#4E9A6B" },
  bitterness: { label: "المرارة", color: "#B0306A" },
  process: { label: "المعالجة", color: "#8A6CC2" },
  origin: { label: "المنشأ", color: "#D9873A" },
  price: { label: "السعر", color: "#3E7DB5" },
};
const BLOCK_ORDER = Object.keys(BLOCKS);

const WORD_KIND = {
  flavor: ["نكهة", "point"], body: ["قوام", "point"], acidity: ["حموضة", "point"], bitterness: ["مرارة", "point"], process: ["معالجة", "point"],
  cheap: ["أرخص", "point"], reference: ["المحصول", "point"], focus: ["اللي عجبك", "point"], cue: ["يشبه", "point"],
  origin: ["منشأ", "filter"], brew: ["تحضير", "filter"], budget: ["ميزانية", "filter"], exclude: ["بدون", "filter"],
  infused: ["منكهة", "filter"], decaf: ["ديكاف", "filter"], saudi: ["سعودية", "filter"],
};

const FUNNEL = {
  all: "كل المحاصيل", stock: "المتوفر", budget: "ضمن الميزانية", cheaper: "بنفس السعر أو أرخص",
  brew: "يناسب التحضير", infused: "بدون منكهة", only_infused: "منكهة بس", exclude: "بدون النكهة المرفوضة",
  type: "قهوة مختصة", decaf: "منزوعة الكافيين", saudi: "قهوة سعودية", origin: "من البلد المطلوب",
};

const STEPS = [
  ["read", "يفهم"],
  ["funnel", "يفلتر"],
  ["target", "يقيس المسافة"],
  ["star", "يختار"],
];

const profileById = Object.fromEntries(profiles.map((p) => [p.profile_id, p]));
const colorOf = (pid) => PROFILE_COLOR[profileById[pid]?.key] || "#8C8A83";
const pctText = (v) => `${Math.round(v * 100)}٪`;
const bodyText = (level, predicted, guess) => {
  if (level) return ar("level", level) + (predicted ? " (متوقع)" : "");
  if (guess) return `تقدير الموديل: ${ar("level", guess[0])} ${pctText(guess[1])}`;
  return "غير معروف";
};
const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function Decision({ data, autoPlay = true }) {
  const explain = data?.explain;
  const [stage, setStage] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);
  const [pick, setPick] = useState(0);
  const hasDots = explain && explain.dots && explain.dots.length > 0;
  const maxStage = hasDots ? 3 : 1;

  useEffect(() => { setStage(0); setPick(0); setPlaying(autoPlay && !reduceMotion()); }, [explain, autoPlay]);
  useEffect(() => {
    if (!playing) return undefined;
    if (stage >= maxStage) { setPlaying(false); return undefined; }
    const t = setTimeout(() => setStage((s) => s + 1), stage === 1 ? 2600 : 2300);
    return () => clearTimeout(t);
  }, [playing, stage, maxStage]);

  if (!explain) return null;
  const cards = Object.fromEntries((data.results || []).map((c) => [c.coffee_id, c]));

  return (
    <section className="decision" aria-label="كيف اختار">
      <header className="decision-head">
        <h2>كيف اختار؟</h2>
        <ol className="decision-steps">
          {STEPS.map(([icon, label], i) => (
            <li key={label}>
              <button type="button" className={`${stage === i ? "now" : ""} ${stage > i ? "done" : ""}`}
                      disabled={i > maxStage} onClick={() => { setPlaying(false); setStage(i); }}>
                <Icon name={icon} size={20} /><span>{label}</span>
              </button>
            </li>
          ))}
        </ol>
        <button type="button" className="secondary small replay" onClick={() => { setStage(0); setPlaying(true); }}>
          <Icon name="play" size={16} />شغّل
        </button>
      </header>

      <div className="decision-body" key={stage}>
        {stage === 0 && <Understand explain={explain} />}
        {stage === 1 && <Funnel explain={explain} />}
        {stage === 2 && hasDots && <Target explain={explain} cards={cards} onPick={(i) => { setPick(i); setPlaying(false); setStage(3); }} />}
        {stage === 3 && hasDots && <Why explain={explain} cards={cards} pick={pick} setPick={setPick} />}
      </div>
      {!hasDots && stage === 1 && explain.mode === "diverse" && (
        <p className="decision-note">ما حددت نكهة، فاخترنا من كل شخصية قهوة (K-Means) أقرب محصول لمركزها.</p>
      )}
    </section>
  );
}

/* ---------- 1) the sentence becomes a point ---------- */
function Understand({ explain }) {
  const ref = explain.reference;
  return (
    <div className="d-understand">
      {explain.words.length > 0 && (
        <p className="d-sentence">
          {explain.words.map((w, i) => {
            const kind = WORD_KIND[w.kind];
            const color = w.family ? FAMILY_COLOR[w.family] : kind && kind[1] === "point" ? "var(--ink)" : null;
            return (
              <span key={i} className={`d-word ${kind ? kind[1] : "plain"}`} style={{ "--c": color || "var(--ink-3)", animationDelay: `${i * 90}ms` }}>
                {w.text}
                {kind && <small>{kind[0]}</small>}
              </span>
            );
          })}
        </p>
      )}
      {ref && (
        <div className="d-ref">
          <span>المحصول اللي عجبك</span>
          <b>{ref.name_ar}</b>
          <em>{ref.roaster_ar}</em>
        </div>
      )}
      <div className="d-point">
        <span className="d-point-title">{ref ? "النقطة = هذا المحصول بكل أجزائه" : "طلبك صار نقطة من هذي الأجزاء"}</span>
        <div className="d-blocks">
          {BLOCK_ORDER.map((b, i) => {
            const on = explain.blocks.includes(b);
            return (
              <div key={b} className={`d-block ${on ? "on" : ""}`} style={{ "--c": BLOCKS[b].color, animationDelay: `${300 + i * 80}ms` }}>
                <b>{BLOCKS[b].label}</b>
                <span>{on ? pctText(explain.weights[b]) : "—"}</span>
                {on && explain.focus && explain.focus !== "overall" && (b === explain.focus || (explain.focus === "flavor" && (b === "notes" || b === "families"))) && <em>×8</em>}
              </div>
            );
          })}
        </div>
      </div>
      {explain.words.length > 0 && (
        <div className="d-legend">
          <span><i className="sw point" />يصير جزء من النقطة</span>
          <span><i className="sw filter" />يصير شرط</span>
        </div>
      )}
    </div>
  );
}

/* ---------- 2) the filters ---------- */
function Funnel({ explain }) {
  const steps = explain.funnel;
  const total = steps[0].count || 1;
  return (
    <div className="d-funnel">
      {steps.map((s, i) => (
        <div key={s.key + i} className={`d-funnel-row ${s.count === 0 ? "zero" : ""} ${i === steps.length - 1 ? "last" : ""}`}
             style={{ animationDelay: `${i * 380}ms` }}>
          <span className="d-funnel-label">{FUNNEL[s.key] || s.key}</span>
          <span className="d-funnel-track">
            <span className="d-funnel-bar" style={{ width: `${Math.max(0.6, (s.count / total) * 100)}%`, animationDelay: `${i * 380}ms` }} />
          </span>
          <b>{num(s.count)}</b>
        </div>
      ))}
      {explain.relaxed && explain.relaxed.length > 0 && (
        <p className="d-funnel-note">ما بقى شي، فخففنا الشرط وجبنا أقرب البدائل.</p>
      )}
    </div>
  );
}

/* ---------- 3) KNN: every coffee by its distance ---------- */
const SIZE = 440, C = SIZE / 2, R0 = 52, R1 = 200;
const radius = (sim) => R0 + (1 - Math.max(0, Math.min(1, sim))) * (R1 - R0);

function Target({ explain, cards, onPick }) {
  const [tip, setTip] = useState(null);
  const dots = useMemo(() => {
    const out = explain.dots.map(([sim, pid, removed, rank], i) => {
      const angle = ((pid * 60 + 5 + ((i * 47) % 50)) * Math.PI) / 180;
      const r = radius(sim);
      return { sim, pid, removed, rank, r, x: C + r * Math.sin(angle), y: C - r * Math.cos(angle), i };
    });
    // the 5 picks: fan out the ones in the same personality so their numbers don't hide each other
    // (only the angle moves inside their own sector; the distance stays exact)
    const picks = out.filter((d) => d.rank).sort((a, b) => a.rank - b.rank);
    const bySector = {};
    picks.forEach((d) => { (bySector[d.pid] = bySector[d.pid] || []).push(d); });
    Object.values(bySector).forEach((group) => {
      const spread = Math.min(12, 48 / group.length);
      group.forEach((d, j) => {
        const deg = group[0].pid * 60 + 30 + (j - (group.length - 1) / 2) * spread;
        const r = d.r + (group.length > 2 ? (j % 2 ? 9 : -9) : 0);
        d.x = C + r * Math.sin((deg * Math.PI) / 180);
        d.y = C - r * Math.cos((deg * Math.PI) / 180);
      });
    });
    return out;
  }, [explain]);
  const kept = dots.filter((d) => !d.removed).length;
  const picks = dots.filter((d) => d.rank).sort((a, b) => a.rank - b.rank);
  const top = Object.fromEntries(explain.top.map((t) => [t.rank, t]));
  const usedProfiles = profiles.filter((p) => dots.some((d) => !d.removed && d.pid === p.profile_id));

  return (
    <div className="d-target">
      <figure className="d-target-fig">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${num(kept)} محصول حسب المسافة، وأقرب 5 مرقمة`}>
          {profiles.map((p) => {
            const a0 = (p.profile_id * 60 * Math.PI) / 180, a1 = ((p.profile_id + 1) * 60 * Math.PI) / 180;
            const path = `M${C},${C} L${C + R1 * Math.sin(a0)},${C - R1 * Math.cos(a0)} A${R1},${R1} 0 0 1 ${C + R1 * Math.sin(a1)},${C - R1 * Math.cos(a1)} Z`;
            return <path key={p.key} d={path} fill={PROFILE_COLOR[p.key]} opacity="0.06" />;
          })}
          {[1, 0.75, 0.5, 0.25, 0].map((s) => (
            <g key={s}>
              <circle cx={C} cy={C} r={radius(s)} className="d-ring" />
              <text x={C - radius(s) - 3} y={C + 4} className="d-ring-label" textAnchor="end">{s ? pctText(s) : ""}</text>
            </g>
          ))}
          {dots.filter((d) => d.removed).map((d) => (
            <circle key={d.i} cx={d.x} cy={d.y} r="2.2" className="d-dot gone" style={{ animationDelay: `${d.removed * 220}ms` }} />
          ))}
          {dots.filter((d) => !d.removed && !d.rank).map((d) => (
            <circle key={d.i} cx={d.x} cy={d.y} r="3.4" fill={colorOf(d.pid)} className="d-dot" />
          ))}
          {picks.map((d) => (
            <line key={`l${d.rank}`} x1={C} y1={C} x2={d.x} y2={d.y} className="d-link" style={{ animationDelay: `${600 + d.rank * 160}ms` }} />
          ))}
          <circle cx={C} cy={C} r="17" className="d-center" />
          <text x={C} y={C + 4.5} textAnchor="middle" className="d-center-label">{explain.reference ? "اللي عجبك" : "طلبك"}</text>
          {picks.map((d) => (
            <g key={`p${d.rank}`} className="d-pick" style={{ animationDelay: `${600 + d.rank * 160}ms` }}
               onMouseEnter={(e) => setTip({ x: e.clientX, y: e.clientY, t: top[d.rank] })} onMouseLeave={() => setTip(null)}
               onClick={() => onPick(d.rank - 1)} role="button" tabIndex={0}
               onKeyDown={(e) => e.key === "Enter" && onPick(d.rank - 1)}>
              <circle cx={d.x} cy={d.y} r="10" fill={colorOf(d.pid)} />
              <text x={d.x} y={d.y + 4.5} textAnchor="middle">{d.rank}</text>
            </g>
          ))}
        </svg>
        {tip && tip.t && (
          <div className="tip" style={{ left: tip.x, top: tip.y }}>
            <b>{tip.t.name_ar}</b><br />{tip.t.roaster_ar}، {pctText(tip.t.score)}
          </div>
        )}
      </figure>
      <div className="d-target-side">
        <p className="d-big"><b>{num(kept)}</b> نقطة تتنافس</p>
        <p className="d-small">كل نقطة محصول. كل ما قربت من المركز، كانت أشبه {explain.reference ? "بالمحصول اللي عجبك" : "بطلبك"}.</p>
        <ol className="d-picks">
          {picks.map((d) => {
            const t = top[d.rank];
            return (
              <li key={d.rank}>
                <button type="button" onClick={() => onPick(d.rank - 1)}>
                  <i style={{ background: colorOf(d.pid) }}>{d.rank}</i>
                  <span>{t?.name_ar || cards[t?.coffee_id]?.coffee_name_ar}</span>
                  <b>{pctText(d.sim)}</b>
                </button>
              </li>
            );
          })}
        </ol>
        <div className="d-colors">
          <span className="d-colors-title">اللون = شخصية القهوة (K-Means)</span>
          {usedProfiles.map((p) => <span key={p.key}><i style={{ background: PROFILE_COLOR[p.key] }} />{p.name.ar}</span>)}
          <span><i className="gone" />استبعده الفلتر</span>
        </div>
      </div>
    </div>
  );
}

/* ---------- 4) why this one ---------- */
function Why({ explain, cards, pick, setPick }) {
  const t = explain.top[Math.min(pick, explain.top.length - 1)];
  if (!t) return null;
  const card = cards[t.coffee_id] || {};
  const ref = explain.reference;
  const wordsOf = (kind) => explain.words.filter((w) => w.kind === kind).map((w) => w.text).join(" ");

  const yours = {
    notes: ref ? ref.notes_ar.slice(0, 4).join("، ") : explain.query_notes_ar.join("، "),
    families: <Fams list={ref ? ref.families : explain.query_families} />,
    body: ref ? bodyText(ref.body_level, false, ref.body_guess) : wordsOf("body"),
    acidity: ar("acidity", ref ? ref.acidity_level : null) || wordsOf("acidity"),
    bitterness: ar("acidity", ref ? ref.bitterness_level : null) || wordsOf("bitterness"),
    process: ar("process", ref ? ref.process : null) || wordsOf("process"),
    origin: ar("country", ref ? ref.origin_country : null) || wordsOf("origin"),
    price: ref ? "قريب منه" : "أرخص",
  };
  const theirs = {
    notes: t.notes_ar.slice(0, 4).map((n) => <span key={n} className={t.shared_notes_ar.includes(n) ? "shared" : ""}>{n}</span>),
    families: <Fams list={t.families} />,
    body: bodyText(t.body_level, t.body_is_predicted, t.body_guess),
    acidity: ar("acidity", t.acidity_level),
    bitterness: ar("acidity", t.bitterness_level),
    process: ar("process", t.process) || "غير معروف",
    origin: ar("country", t.origin_country) || "غير معروف",
    price: card.price_per_100g_sar ? `${card.price_per_100g_sar} ريال لكل 100 جرام` : "",
  };

  return (
    <div className="d-why">
      <div className="d-why-tabs" role="tablist">
        {explain.top.map((x, i) => (
          <button key={x.rank} type="button" role="tab" aria-selected={i === pick} className={i === pick ? "on" : ""}
                  onClick={() => setPick(i)}>
            <i style={{ background: colorOf(x.profile_id) }}>{x.rank}</i>{pctText(x.score)}
          </button>
        ))}
      </div>
      <h3 className="d-why-name">{t.name_ar}<span>{t.roaster_ar}</span></h3>

      <div className="d-stack" aria-label={`التطابق ${pctText(t.score)}`}>
        <div className="d-stack-bar">
          {t.parts.filter((p) => p.points > 0.004).map((p, i) => (
            <span key={p.key} style={{ width: `${p.points * 100}%`, background: BLOCKS[p.key].color, animationDelay: `${i * 120}ms` }}
                  title={`${BLOCKS[p.key].label}: ${pctText(p.points)}`} />
          ))}
          <em style={{ width: `${(1 - t.score) * 100}%` }} />
        </div>
        <b>{pctText(t.score)}</b>
      </div>

      <div className="d-rows">
        <div className="d-row head"><span /><span>{ref ? "اللي عجبك" : "طلبك"}</span><span>هذا المحصول</span><span>التطابق × الوزن</span></div>
        {t.parts.map((p) => (
          <div className="d-row" key={p.key}>
            <span className="d-row-name"><i style={{ background: BLOCKS[p.key].color }} />{BLOCKS[p.key].label}</span>
            <span>{yours[p.key] || "—"}</span>
            <span className="d-theirs">{theirs[p.key] || "—"}</span>
            <span className="d-math">
              <span className="d-meter"><span style={{ width: `${p.match * 100}%`, background: BLOCKS[p.key].color }} /></span>
              <small>{pctText(p.match)} × {pctText(p.weight)} = <b>{pctText(p.points)}</b></small>
            </span>
          </div>
        ))}
      </div>
      {explain.skipped.length > 0 && (
        <p className="d-skip"><Icon name="cards" size={18} />تخطينا {explain.skipped.map((s) => s.name_ar).join("، ")} عشان ما يتكرر نفس المحمصة أو نفس المحصول.</p>
      )}
    </div>
  );
}

function Fams({ list }) {
  if (!list || !list.length) return "—";
  return (
    <span className="d-fams">
      {list.map((f) => <span key={f}><i style={{ background: FAMILY_COLOR[f] }} />{FAMILY_NAME[f]}</span>)}
    </span>
  );
}
