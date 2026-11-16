// The presentation: one idea per slide, visuals first, very little text.
// Every number comes from models/report.json (written by the notebook).
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { api } from "./api.js";
import { BarList, GroupedBars, Histogram, LineChart } from "./Charts.jsx";
import Demo from "./Demo.jsx";
import Decision from "./Decision.jsx";
import FlavorWheel from "./FlavorWheel.jsx";
import { CountUp, FlavorDonut, FlipCard, Icon, MessyChips, Ring } from "./Fun.jsx";
import { FAMILIES, FAMILY_COLOR, FAMILY_NAME, FAMILY_QUERY, PROFILE_COLOR, REPO_URL, SERIES, TEAM, ar, num, pct, profiles, report } from "./data.js";

const SIZES_AR = ["250 جرام", "250 جم", "250ج", "250 غرام", "250جم", "250غ", "250جرام", "0.25 كيلو"];
const HEIRLOOM_AR = ["هيرلوم", "هيرليوم", "إيرليوم", "هارليوم", "ايليريوم", "هيريليوم", "الهيرلوم", "الفصائل المتوارثة"];

const centroidShares = (p) => Object.fromEntries(FAMILIES.map((f) => [f, p.centroid[["fruity", "citrus", "floral", "chocolate", "nutty", "caramel_sweet", "spice", "tea"].indexOf(f)]]));

export function useSlides(goTry) {
  const d = report.data;
  const prec = report.precision;
  const at50 = report.body_model.threshold_table.find((r) => r.min_confidence === 0.5);
  const twinRows = report.twin_test.filter((r) => r.representation !== "Random ranking");
  const twinBest = Math.max(...twinRows.map((r) => r.hit_at_5));
  const twinRatio = twinBest / report.twin_test.find((r) => r.representation === "Random ranking").hit_at_5;
  const ms = Math.round(report.variety.ms_per_request);

  return [
    {
      id: "hello",
      render: () => (
        <div className="slide-hero">
          <div className="hero-text">
            <h1 className="hero-title">محتار وش تشتري؟</h1>
            <p className="hero-line">قل وش تحب، ونطلع لك أقرب 5 محاصيل من {num(d.n_coffees)} محصول.</p>
            <div className="hero-stats">
              <span><b><CountUp to={d.n_coffees} /></b>محصول</span>
              <span><b><CountUp to={d.n_roasters} /></b>محمصة سعودية</span>
              <span><b><CountUp to={d.n_sites} /></b>موقع</span>
            </div>
            <div className="hero-actions">
              <button type="button" className="primary big" onClick={() => goTry()}>جربه الحين</button>
              <span className="hint">أو اضغط أي نكهة في العجلة</span>
            </div>
          </div>
          <FlavorWheel onPick={({ family, noteAr }) => goTry(noteAr || FAMILY_QUERY[family])} />
        </div>
      ),
    },
    {
      id: "problem",
      render: () => (
        <div>
          <h2 className="slide-title">كل محمصة تكتب بطريقتها</h2>
          <div className="slide-grid problem-grid">
            <div className="rings">
              <Ring value={0.78} color="var(--rose)" label="بدون درجة تحميص" />
              <Ring value={0.70} color="var(--gold)" label="بدون قوام" />
              <Ring value={42 / d.n_coffees} color="var(--roast)" label="بدون نكهات" />
            </div>
            <MessyChips cleanLabel="نظفها" messyLabel="رجعها"
                        groups={[{ items: SIZES_AR, clean: "250 جرام", color: "var(--sage)" },
                                 { items: HEIRLOOM_AR, clean: "هيرلوم", color: "var(--gold)" }]} />
          </div>
        </div>
      ),
    },
    {
      id: "data",
      render: () => (
        <div>
          <h2 className="slide-title">بيانات نظيفة</h2>
          <div className="slide-grid two">
            <div className="counters">
              {[["قيمة ناقصة", d.missing_before, 0], ["خلية بالعربي", 2215, 0], ["اسم منطقة", 201, 110], ["اسم سلالة", 137, 63]].map(([label, from, to], i) => (
                <div className="counter-tile" key={label}>
                  <s>{num(from)}</s>
                  <b><CountUp from={from} to={to} delay={200 + i * 150} duration={1400} /></b>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            <div className="chart-box">
              <h3>من وين تجي؟</h3>
              <BarList color={SERIES.ours} rows={Object.entries(d.top_origins).map(([k, v]) => ({ label: ar("country", k) || k, value: v }))} />
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "eda",
      render: () => (
        <div>
          <h2 className="slide-title">وش تقول البيانات</h2>
          <div className="slide-grid two">
            <div className="chart-box">
              <p className="big-fact"><b>{pct(d.families.fruity / d.n_coffees)}</b> فاكهية</p>
              <BarList rows={[...FAMILIES].sort((a, b) => d.families[b] - d.families[a])
                .map((f) => ({ label: FAMILY_NAME[f], value: d.families[f], color: FAMILY_COLOR[f] }))} />
            </div>
            <div className="chart-box">
              <p className="big-fact"><b>{d.median_price_100g}</b> ريال لكل 100 جرام</p>
              <Histogram bins={d.price_hist} lo={0} hi={60} median={d.median_price_100g} color={SERIES.keyword}
                         medianLabel="الوسيط" axisLabel="السعر لكل 100 جرام" />
              <p className="note-line">اليمني والسعودي أغلى: <b>{d.continent_median["Arabian Peninsula"].toFixed(0)}</b> مقابل <b>{d.continent_median.Africa.toFixed(0)}</b></p>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "idea",
      render: () => (
        <div>
          <h2 className="slide-title">ثلاث طرق توصلك لقهوتك</h2>
          <div className="ways">
            {[["text", "chat", "قلها بكلامك", "«أبي شي فاكهي للفلتر»"],
              ["similar", "heart", "اختر محصول عجبك", "«كولومبي ويلا، عجبني قوامه»"],
              ["profile", "cards", "اختر شخصية", "ست بطاقات للمبتدئين"]].map(([mode, icon, title, example]) => (
              <button type="button" className="way" key={mode} onClick={() => goTry(null, mode)}>
                <span className="way-icon"><Icon name={icon} size={40} /></span>
                <b>{title}</b>
                <span>{example}</span>
              </button>
            ))}
          </div>
          <div className="answer-strip">
            <span><Icon name="star" size={22} />5 محاصيل</span>
            <span><Icon name="scale" size={22} />نسبة تطابق</span>
            <span><Icon name="tag" size={22} />السبب</span>
          </div>
        </div>
      ),
    },
    {
      id: "type",
      render: () => (
        <div>
          <h2 className="slide-title">Supervised ولا Unsupervised؟</h2>
          <p className="one-liner">ما عندنا تقييمات مستخدمين، فالأساس <b>KNN</b>. والباقي يكمل الناقص.</p>
          <div className="flips">
            <FlipCard tone="content" front={<><Icon name="target" /><b>K-Nearest Neighbors</b><em>Unsupervised</em></>}
                      back={<><b>طلبك نقطة</b><span>ونجيب أقرب 5 محاصيل لها</span></>} />
            <FlipCard tone="sup" front={<><Icon name="drop" /><b>نكهات 42 محصول</b><em>Supervised</em></>}
                      back={<><b>Random Forest</b><span>تعلمت من 527 محصول، وتغذي KNN</span></>} />
            <FlipCard tone="sup" front={<><Icon name="cards" /><b>قوام 397 محصول</b><em>Supervised</em></>}
                      back={<><b>Random Forest</b><span>احتمالاتها تدخل في KNN</span></>} />
            <FlipCard tone="unsup2" front={<><Icon name="star" /><b>شخصيات القهوة</b><em>Unsupervised</em></>}
                      back={<><b>K-Means Clustering</b><span>6 مجموعات</span></>} />
            <FlipCard tone="rules" front={<><Icon name="words" /><b>الحموضة والمرارة وفهم العربي</b><em>Rule-based</em></>}
                      back={<><b>قواعد نختبرها</b><span>ما فيه إجابات نتعلم منها</span></>} />
          </div>
          <p className="tap-hint">اضغط أي بطاقة</p>
        </div>
      ),
    },
    { id: "how", render: () => <PipelineSlide /> },
    {
      id: "profiles",
      render: () => (
        <div>
          <h2 className="slide-title">ست شخصيات للقهوة</h2>
          <div className="slide-grid wide-left">
            <div className="persona-grid">
              {profiles.map((p) => (
                <button type="button" className="persona" key={p.key} style={{ "--accent": PROFILE_COLOR[p.key] }}
                        onClick={() => goTry(null, "profile")}>
                  <FlavorDonut shares={centroidShares(p)} size={70} />
                  <b>{p.name.ar}</b>
                  <span>{num(p.n_coffees)} محصول</span>
                </button>
              ))}
            </div>
            <div className="chart-box">
              <h3>كم مجموعة؟</h3>
              <LineChart color={SERIES.ours} highlight={6} yLabel="Silhouette Score"
                         points={report.kmeans.k_table.map((r) => ({ x: r.k, y: r.silhouette }))} />
              <p className="note-line">أكثر من 6 بطاقات كثير على المبتدئ</p>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "gaps",
      render: () => (
        <div>
          <h2 className="slide-title">نكمل الناقص</h2>
          <div className="slide-grid two">
            <div className="chart-box">
              <h3><Icon name="drop" size={22} /> نكهات الـ 42</h3>
              <BarList max={1} format={(v) => v.toFixed(2)} refLine={0.5} refLabel="الخط المتقطع = تخمين"
                       rows={Object.entries(report.flavor_model.auc_by_family["Random Forest"]).sort((a, b) => b[1] - a[1])
                         .map(([f, v]) => ({ label: FAMILY_NAME[f], value: v, color: FAMILY_COLOR[f] }))} />
              <p className="note-line">Random Forest <b>{report.flavor_model.auc_by_model["Random Forest"].toFixed(2)}</b> مقابل Logistic Regression <b>{report.flavor_model.auc_by_model["Logistic Regression"].toFixed(2)}</b></p>
            </div>
            <div className="chart-box body-box">
              <h3><Icon name="cards" size={22} /> قوام الـ 397</h3>
              <Ring value={at50.accuracy_when_shown} color="var(--sage)" size={150} label="صح لما يكون متأكد" />
              <div className="mini-facts">
                <span><b>{report.body_model.n_predicted_shown}</b>نعرضها بكلمة «متوقع»</span>
                <span><b>4</b>موديلات قارناها، و Random Forest من أدقها احتمالات</span>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "results",
      render: () => (
        <div>
          <h2 className="slide-title">هل يشتغل صح؟</h2>
          <div className="stat-tiles">
            <div><b><CountUp to={report.understanding.n_heldout} />/{report.understanding.n_heldout}</b><span>طلب جديد انفهم بالكامل</span></div>
            <div><b><CountUp to={Math.round(prec["Held-out only"].ours * 100)} />٪</b><span>من النتائج تطابق الطلب</span></div>
            <div><b>{twinRatio.toFixed(1)}×</b><span>يلقى «التوأم» أكثر من العشوائي</span></div>
            <div><b><CountUp to={ms} /></b><span>مللي ثانية لكل طلب</span></div>
          </div>
          <div className="chart-box">
            <GroupedBars max={1} format={(v) => v.toFixed(2)} height={190}
                         groups={["طلبات عربية", "طلبات إنجليزية", "طلبات جديدة"]}
                         series={[
                           { name: "موديلنا", color: SERIES.ours, values: [prec.Arabic.ours, prec.English.ours, prec["Held-out only"].ours] },
                           { name: "بحث بالكلمات", color: SERIES.keyword, values: [prec.Arabic.keyword_search, prec.English.keyword_search, prec["Held-out only"].keyword_search] },
                           { name: "عشوائي", color: SERIES.baseline, values: [prec.Arabic.random, prec.English.random, prec["Held-out only"].random] },
                         ]} />
            {report.team_eval && (
              <p className="note-line">اختبار مستقل كتبته دانية ({report.team_eval.n_queries} طلب): انفهم <b>{Math.round(report.team_eval.understood_first_try_pct)}٪</b> من أول مرة، و <b>{Math.round(report.team_eval.understood_pct)}٪</b> بعد ما أضفنا المرارة</p>
            )}
          </div>
        </div>
      ),
    },
    { id: "demo", render: () => <LiveSlide /> },
    {
      id: "hood",
      render: () => (
        <div>
          <h2 className="slide-title">من الداخل</h2>
          <div className="arch">
            {[["screen", "Frontend"], ["server", "FastAPI"], ["target", "محرك KNN"], ["table", "البيانات"], ["book", "Notebook"]].map(([icon, label], i, all) => (
              <div className="arch-step" key={label}>
                <div className={`arch-node ${i === all.length - 1 ? "offline" : ""}`}><Icon name={icon} size={34} /><b>{label}</b></div>
                {i < all.length - 1 && <span className={`arch-arrow ${i === all.length - 2 ? "back" : ""}`} />}
              </div>
            ))}
          </div>
          <div className="chips-row">
            <span>نشر واحد</span><span>6 API endpoints</span><span>{ms} مللي ثانية</span><span>بدون scikit-learn في الخادم</span>
          </div>
        </div>
      ),
    },
    {
      id: "next",
      render: () => (
        <div>
          <h2 className="slide-title">مَذاق كمشروع تجاري</h2>
          <div className="next-tiles">
            <div><Icon name="tag" size={34} /><b>عمولة على كل بيعة</b><span>رابط شراء لكل محمصة</span></div>
            <div><Icon name="table" size={34} /><b>لوحة للمحامص</b><span>وش يطلب الناس وما لقوه</span></div>
            <div><Icon name="star" size={34} /><b>صندوق شهري</b><span>قهوة على ذوقك كل شهر</span></div>
            <div><Icon name="thumbs" size={34} /><b>زر عجبني</b><span>تقييماتكم تحسن الموديل</span></div>
          </div>
          <div className="team">
            {TEAM.map((m) => <div key={m.name} className="member"><b>{m.name}</b></div>)}
          </div>
          <p className="thanks">شكرًا لكم</p>
        </div>
      ),
    },
  ];
}

const PIPE_EXAMPLE = "أبي شي فاكهي للفلتر بأقل من 70 ريال";

function PipelineSlide() {
  const [q, setQ] = useState(PIPE_EXAMPLE);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);

  const runIt = async () => {
    setBusy(true);
    try {
      setRes(await api.recommend(q, "ar", {}, 5));
    } catch {
      setRes({ error: true });
    }
    setBusy(false);
  };

  return (
    <div>
      <h2 className="slide-title">كيف يختار؟</h2>
      <div className="live-run">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && runIt()} aria-label="الطلب" />
        <button type="button" className="primary" onClick={runIt} disabled={busy}><Icon name="play" size={16} />شغّله</button>
      </div>
      {!res && (
        <div className="pipe-placeholder">
          {[["read", "يفهم"], ["funnel", "يفلتر"], ["target", "يقيس المسافة"], ["star", "يختار"]].map(([icon, label]) => (
            <span key={label}><Icon name={icon} size={34} /><b>{label}</b></span>
          ))}
        </div>
      )}
      {res && res.error && <p className="alert">صار خطأ، جرب مرة ثانية.</p>}
      {res && !res.error && <Decision data={res} />}
    </div>
  );
}

function LiveSlide() {
  const [qr, setQr] = useState("");
  useEffect(() => {
    QRCode.toString(window.location.origin + "/#/try", { type: "svg", margin: 0, color: { dark: "#2A1F1A", light: "#00000000" } })
      .then(setQr).catch(() => setQr(""));
  }, []);
  return (
    <div className="slide-live">
      <div className="live-head">
        <h2 className="slide-title">جربه بنفسك</h2>
        {qr && (
          <div className="qr">
            <div className="qr-code" dangerouslySetInnerHTML={{ __html: qr }} />
            <span><Icon name="phone" size={20} /> امسح وجرب من جوالك</span>
          </div>
        )}
      </div>
      <Demo compact />
    </div>
  );
}
