// The live demo: the three ways of the handoff doc, talking to the FastAPI endpoints (always in Arabic).
import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { T } from "./i18n.js";
import { FAMILY_COLOR, FAMILY_NAME, PROFILE_COLOR, REASONS, ar, num, profiles as PROFILE_DATA } from "./data.js";
import { FlavorDonut, FlavorRibbon, Icon } from "./Fun.jsx";
import Decision from "./Decision.jsx";

const FAMILY_ORDER = ["fruity", "citrus", "floral", "chocolate", "nutty", "caramel_sweet", "spice", "tea"];
const sharesOf = (id) => {
  const p = PROFILE_DATA.find((x) => x.profile_id === id);
  return p ? Object.fromEntries(FAMILY_ORDER.map((f, i) => [f, p.centroid[i]])) : {};
};

const FOCUSES = ["overall", "flavor", "body", "acidity", "bitterness", "price", "origin", "process"];
const LANG = "ar";

export default function Demo({ request, compact = false }) {
  const [mode, setMode] = useState("text");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({ max_price_sar: "", brew_method: "", exclude_infused: false });
  const [search, setSearch] = useState("");
  const [suggestions, setSuggestions] = useState(null);
  const [picked, setPicked] = useState(null);
  const [focus, setFocus] = useState("overall");
  const [profiles, setProfiles] = useState([]);
  const [state, setState] = useState({ loading: false, error: false, data: null });
  const lastAction = useRef(null);
  const resultsRef = useRef(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  async function run(action) {
    lastAction.current = action;
    setState({ loading: true, error: false, data: null });
    if (window.innerWidth < 980 && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    try {
      setState({ loading: false, error: false, data: await action(filtersRef.current) });
    } catch {
      setState({ loading: false, error: true, data: null });
    }
  }

  useEffect(() => { api.profiles(LANG).then(setProfiles).catch(() => setProfiles([])); }, []);

  // requests coming from outside (a click on the flavor wheel)
  useEffect(() => {
    if (!request) return;
    if (!request.query) { setMode(request.mode || "text"); return; }
    setMode("text");
    setQuery(request.query);
    run((f) => api.recommend(request.query, LANG, f));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request]);

  // autocomplete for "liked a coffee"
  useEffect(() => {
    if (!search.trim() || picked) { setSuggestions(null); return undefined; }
    const timer = setTimeout(() => {
      api.coffees(search.trim(), 8).then(setSuggestions).catch(() => setSuggestions([]));
    }, 180);
    return () => clearTimeout(timer);
  }, [search, picked]);

  const submitText = (text) => {
    const q = (text ?? query).trim();
    if (!q) return;
    setQuery(q);
    run((f) => api.recommend(q, LANG, f));
  };
  const showSimilar = (id, f = focus) => run((fl) => api.similar(id, f, LANG, fl));

  return (
    <div className={`demo ${compact ? "demo-compact" : ""}`}>
      <div className="demo-ask">
        {!compact && <h1 className="demo-question">{T.question}</h1>}
        <div className="tabs" role="tablist">
          {[["text", T.tabText, "chat"], ["similar", T.tabSimilar, "heart"], ["profile", T.tabProfile, "cards"]].map(([id, label, icon]) => (
            <button key={id} role="tab" aria-selected={mode === id} className={mode === id ? "on" : ""}
                    onClick={() => setMode(id)}><Icon name={icon} size={22} /><span>{label}</span></button>
          ))}
        </div>

        {mode === "text" && (
          <form className="panel" onSubmit={(e) => { e.preventDefault(); submitText(); }}>
            <label htmlFor="q" className="field-label">{T.textLabel}</label>
            <textarea id="q" rows={compact ? 2 : 3} value={query} placeholder={T.textPlaceholder}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitText(); } }} />
            <div className="examples">
              <span>{T.tryExample}</span>
              {T.examples.map((ex) => (
                <button type="button" key={ex} className="chip-btn" onClick={() => submitText(ex)}>{ex}</button>
              ))}
            </div>
            <button type="submit" className="primary" disabled={!query.trim()}>{T.find}</button>
          </form>
        )}

        {mode === "similar" && (
          <div className="panel">
            <label htmlFor="s" className="field-label">{T.searchLabel}</label>
            {picked ? (
              <div className="picked">
                <div><b>{picked.coffee_name_ar}</b><span>{picked.roaster_ar}</span></div>
                <button type="button" className="link" onClick={() => { setPicked(null); setSearch(""); }}>{T.change}</button>
              </div>
            ) : (
              <div className="combo">
                <input id="s" value={search} autoComplete="off" placeholder={T.searchPlaceholder}
                       onChange={(e) => setSearch(e.target.value)} />
                {suggestions && (
                  <ul className="suggest" role="listbox">
                    {suggestions.length === 0 && <li className="muted">{T.noMatches}</li>}
                    {suggestions.map((c) => (
                      <li key={c.coffee_id}>
                        <button type="button" onClick={() => { setPicked(c); setSuggestions(null); }}>
                          <b>{c.coffee_name_ar}</b>
                          <span>{c.roaster_ar}{c.out_of_stock ? `، ${T.outOfStock}` : ""}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <div className="field-label">{T.likedWhat}</div>
            <div className="segmented wrap">
              {FOCUSES.map((f) => (
                <button key={f} type="button" className={focus === f ? "on" : ""} onClick={() => setFocus(f)}>{T.focus[f]}</button>
              ))}
            </div>
            <button type="button" className="primary" disabled={!picked} onClick={() => showSimilar(picked.coffee_id)}>
              {T.showSimilar}
            </button>
          </div>
        )}

        {mode === "profile" && (
          <div className="panel">
            <div className="field-label">{T.profileLabel}</div>
            <div className="profiles">
              {profiles.map((p) => (
                <button key={p.profile_id} type="button" className="profile-card"
                        style={{ "--accent": PROFILE_COLOR[p.key] }}
                        onClick={() => run((f) => api.byProfile(p.profile_id, LANG, f))}>
                  <FlavorDonut shares={sharesOf(p.profile_id)} size={44} />
                  <span className="profile-text">
                    <b>{p.name}</b>
                    <span className="profile-notes">{p.top_notes_ar.slice(0, 3).join("، ")}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <fieldset className="filters">
          <legend>{T.filters}</legend>
          <label className="filter-budget">
            <span>{T.budget}</span>
            <input type="number" inputMode="numeric" min="0" step="5" value={filters.max_price_sar}
                   placeholder="70" onChange={(e) => setFilters({ ...filters, max_price_sar: e.target.value })} />
          </label>
          <div className="filter-brew">
            <span>{T.brew}</span>
            <div className="segmented">
              {[["", T.any], ["espresso", T.espresso], ["filter", T.filter]].map(([v, label]) => (
                <button key={v || "any"} type="button" className={filters.brew_method === v ? "on" : ""}
                        onClick={() => setFilters({ ...filters, brew_method: v })}>{label}</button>
              ))}
            </div>
          </div>
          <label className="check">
            <input type="checkbox" checked={filters.exclude_infused}
                   onChange={(e) => setFilters({ ...filters, exclude_infused: e.target.checked })} />
            <span>{T.noInfused}</span>
          </label>
        </fieldset>
      </div>

      <section className="demo-results" ref={resultsRef} aria-live="polite">
        <Results state={state} onRetry={() => lastAction.current && run(lastAction.current)}
                 onSimilar={(id, f) => showSimilar(id, f)} />
      </section>
    </div>
  );
}

function Results({ state, onRetry, onSimilar }) {
  const [showWhy, setShowWhy] = useState(() => window.innerWidth >= 980);
  if (state.loading) {
    return (
      <div className="results">
        <p className="loading">{T.loading}<span className="dots" /></p>
        {[0, 1, 2].map((i) => <div className="card skeleton" key={i} />)}
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="results">
        <div className="alert">{T.error}</div>
        <button type="button" className="secondary" onClick={onRetry}>{T.retry}</button>
      </div>
    );
  }
  const data = state.data;
  if (!data) {
    return (
      <div className="results empty">
        <h2>{T.emptyTitle}</h2>
        <p>{T.emptyBody}</p>
      </div>
    );
  }
  return (
    <div className="results">
      {data.status === "no_results" ? (
        <div className="alert"><b>{T.noResultsTitle}</b><p>{data.message}</p></div>
      ) : (
        <p className="message">{data.message}</p>
      )}
      {data.status !== "clarify" && !data.explain && <Understood u={data.understood} />}
      {data.status !== "clarify" && data.explain && (showWhy
        ? <Decision data={data} />
        : (
          <button type="button" className="why-open" onClick={() => setShowWhy(true)}>
            <Icon name="target" size={26} /><span><b>كيف اختار؟</b>شوف الخطوات</span>
          </button>
        ))}
      {data.status === "clarify" && (
        <div className="options">
          {data.options.map((o) => (
            <button key={o.coffee_id} type="button" className="option"
                    onClick={() => onSimilar(o.coffee_id, data.understood.focus || "overall")}>{o.label}</button>
          ))}
        </div>
      )}
      <div className="cards">
        {data.results.map((c) => <Card key={c.coffee_id} c={c} onSimilar={onSimilar} />)}
      </div>
    </div>
  );
}

export function Understood({ u, bare = false }) {
  const L = T.understoodLabels;
  const chips = [];
  if (u.reference_coffee_name) {
    chips.push([`${L.like}: ${u.reference_coffee_name}`]);
    if (u.focus && u.focus !== "overall") chips.push([`${L.focus}: ${T.focus[u.focus]}`]);
  } else {
    (u.flavors || []).forEach((f) => chips.push([FAMILY_NAME[f], FAMILY_COLOR[f]]));
    (u.excluded_flavors || []).forEach((f) => chips.push([`${L.no} ${FAMILY_NAME[f]}`]));
  }
  if (u.body) chips.push([`${L.body} ${ar("level", u.body)}`]);
  if (u.acidity) chips.push([`${L.acidity} ${ar("acidity", u.acidity)}`]);
  if (u.bitterness) chips.push([`${L.bitterness} ${ar("acidity", u.bitterness)}`]);
  if (u.process) chips.push([ar("process", u.process)]);
  if (u.origin && ar("country", u.origin)) chips.push([ar("country", u.origin)]);
  if (u.brew_method) chips.push([`${L.brew}: ${ar("brew", u.brew_method)}`]);
  if (u.max_price_sar != null) chips.push([`${L.budget} ${u.max_price_sar} ${T.sar}`]);
  if (u.decaf) chips.push([L.decaf]);
  if (u.saudi_coffee) chips.push([L.saudi]);
  if (u.exclude_infused) chips.push([L.noInfused]);
  if (u.cheap) chips.push([L.cheap]);
  if (!chips.length) return null;
  return (
    <div className="understood">
      {!bare && <span>{T.understood}</span>}
      {chips.filter(([text]) => text).map(([text, color], i) => (
        <span key={i} className="u-chip">{color && <i style={{ background: color }} />}{text}</span>
      ))}
    </div>
  );
}

function Card({ c, onSimilar }) {
  const pct = Math.round(c.match_score * 100);
  const reasons = (c.reasons || []).map((r) => REASONS[r]).filter(Boolean);
  const city = ar("city", c.roaster_city);
  return (
    <article className="card">
      <FlavorRibbon families={c.families} />
      <div className="card-top">
        <div className="card-title">
          <h3>{c.coffee_name_ar}</h3>
          <p>{c.roaster_ar}{city ? `، ${city}` : ""}</p>
        </div>
        <div className="score" style={{ "--p": pct }} aria-label={`${T.match} ${pct}٪`}>
          <b>{pct}٪</b><span>{T.match}</span>
        </div>
      </div>
      <div className="price">
        <b>{c.price_sar} {T.sar}</b>
        <span>{c.weight_g} {T.g}</span>
        <span className="per">{c.price_per_100g_sar} {T.sar} {T.perGram}</span>
        {c.price_is_estimated && <span className="tag">{T.estimatedPrice}</span>}
      </div>
      <dl className="facts">
        <div><dt>{T.origin}</dt><dd>{ar("country", c.origin_country) || T.unknown}{c.region_ar ? `، ${c.region_ar}` : ""}</dd></div>
        <div><dt>{T.process}</dt><dd>{ar("process", c.process) || T.unknown}</dd></div>
        <div><dt>{T.body}</dt><dd>{ar("level", c.body_level) || T.unknown}{c.body_is_predicted && <span className="tag">{T.predicted} {Math.round(c.body_confidence * 100)}٪</span>}</dd></div>
        <div><dt>{T.acidity}</dt><dd>{ar("acidity", c.acidity_level) || T.unknown}{c.acidity_is_estimated && <span className="tag">{T.estimated}</span>}</dd></div>
        <div><dt>{T.bitterness}</dt><dd>{ar("acidity", c.bitterness_level) || T.unknown}{c.bitterness_is_estimated && <span className="tag">{T.estimated}</span>}</dd></div>
      </dl>
      <div className="notes">
        {c.tasting_notes_ar.map((n) => <span key={n} className="note">{n}</span>)}
        {c.tasting_notes_are_predicted && <span className="tag">{T.predictedFlavors}</span>}
      </div>
      {reasons.length > 0 && <ul className="reasons">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
      <div className="card-actions">
        <a className="primary small" href={c.product_url} target="_blank" rel="noopener noreferrer">{T.buy}</a>
        <button type="button" className="secondary small" onClick={() => onSimilar(c.coffee_id, "overall")}>{T.similar}</button>
      </div>
    </article>
  );
}
