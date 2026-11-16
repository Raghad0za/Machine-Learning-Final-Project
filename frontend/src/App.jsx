import { useCallback, useEffect, useRef, useState } from "react";
import Demo from "./Demo.jsx";
import { useSlides } from "./Slides.jsx";
import { T } from "./i18n.js";

function readHash() {
  const h = window.location.hash.replace(/^#\/?/, "");
  if (h.startsWith("try")) return { view: "try", slide: 0 };
  const m = h.match(/^story\/(\d+)/);
  return { view: "story", slide: m ? Math.max(0, parseInt(m[1], 10) - 1) : 0 };
}

export default function App() {
  const [{ view, slide }, setRoute] = useState(readHash);
  const [request, setRequest] = useState(null);
  const touch = useRef(null);

  const goTry = useCallback((query, mode) => {
    if (query || mode) setRequest({ query, mode, id: Date.now() });
    setRoute({ view: "try", slide: 0 });
    window.scrollTo(0, 0);
  }, []);

  const slides = useSlides(goTry);
  const count = slides.length;
  const go = useCallback((i) => setRoute({ view: "story", slide: Math.min(count - 1, Math.max(0, i)) }), [count]);

  useEffect(() => {
    const target = view === "try" ? "#/try" : `#/story/${slide + 1}`;
    if (window.location.hash !== target) window.history.replaceState(null, "", target);
  }, [view, slide]);

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // keyboard: a presentation clicker sends Right/PageDown for "next", whatever the page direction
  useEffect(() => {
    if (view !== "story") return undefined;
    const onKey = (e) => {
      const tag = (e.target.tagName || "").toLowerCase();
      if (["input", "textarea", "select"].includes(tag) || e.target.isContentEditable) return;
      if (e.key === "ArrowRight" || e.key === "PageDown" || (e.key === " " && tag !== "button")) { e.preventDefault(); go(slide + 1); }
      if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(slide - 1); }
      if (e.key === "Home") go(0);
      if (e.key === "End") go(count - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view, slide, go, count]);

  const onTouchStart = (e) => { touch.current = [e.touches[0].clientX, e.touches[0].clientY]; };
  const onTouchEnd = (e) => {
    if (!touch.current) return;
    const dx = e.changedTouches[0].clientX - touch.current[0];
    const dy = e.changedTouches[0].clientY - touch.current[1];
    touch.current = null;
    if (Math.abs(dx) < 70 || Math.abs(dy) > 60) return;
    go(slide + (dx > 0 ? 1 : -1)); // right to left reading: swiping right brings the next slide
  };

  return (
    <div className={`app view-${view}`}>
      <header className="topbar">
        <button type="button" className="brand" onClick={() => go(0)}>
          <svg viewBox="0 0 32 32" aria-hidden="true"><ellipse cx="16" cy="16" rx="9" ry="12.5" transform="rotate(-30 16 16)" /><path d="M11.5 5.5c5.5 6 3.5 15 9 21" transform="rotate(-30 16 16)" /></svg>
          <span>{T.brand}</span>
        </button>
        <nav className="nav">
          <button type="button" className={view === "story" ? "on" : ""} onClick={() => go(slide)}>{T.navStory}</button>
          <button type="button" className={view === "try" ? "on" : ""} onClick={() => goTry()}>{T.navTry}</button>
        </nav>
      </header>

      {view === "story" ? (
        <main className="stage" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
          <section className={`slide slide-${slides[slide].id}`} key={slides[slide].id}
                   aria-roledescription={T.slide} aria-label={`${slide + 1} ${T.of} ${count}`}>
            {slides[slide].render()}
          </section>
          <footer className="slide-nav">
            <button type="button" className="secondary small" onClick={() => go(slide - 1)} disabled={slide === 0}>{T.prev}</button>
            <div className="dots" role="tablist" aria-label="الشرائح">
              {slides.map((s, i) => (
                <button key={s.id} type="button" role="tab" aria-selected={i === slide}
                        className={`dot ${i === slide ? "now" : i < slide ? "seen" : ""}`}
                        aria-label={`${T.slide} ${i + 1}`} onClick={() => go(i)}>{i === slide ? `${i + 1} ${T.of} ${count}` : ""}</button>
              ))}
            </div>
            <button type="button" className="primary small" onClick={() => go(slide + 1)} disabled={slide === count - 1}>{T.next}</button>
          </footer>
        </main>
      ) : (
        <main className="try-page">
          <Demo request={request} />
        </main>
      )}
    </div>
  );
}
