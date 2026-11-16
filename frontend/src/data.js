// Shared constants. The numbers come from the notebook (models/report.json), never typed by hand.
import report from "../../models/report.json";
import profiles from "../../models/profiles.json";

export { report, profiles };

// Order chosen so neighbours on the wheel are easy to tell apart (validated for color blindness).
export const FAMILIES = ["fruity", "citrus", "floral", "nutty", "spice", "caramel_sweet", "chocolate", "tea"];

export const FAMILY_COLOR = {
  fruity: "#C25B5B",
  citrus: "#C9A227",
  floral: "#8A6CC2",
  nutty: "#AB7B35",
  spice: "#A8436E",
  caramel_sweet: "#D9873A",
  chocolate: "#8F4522",
  tea: "#4E9A6B",
};

export const FAMILY_NAME = {
  fruity: "فاكهي", citrus: "حمضيات", floral: "زهري", nutty: "مكسرات", spice: "بهارات",
  caramel_sweet: "كراميل وحلو", chocolate: "شوكولاتة", tea: "شاي",
};

// What we send to the API when someone clicks a family on the wheel.
export const FAMILY_QUERY = {
  fruity: "فاكهي", citrus: "حمضيات", floral: "زهري", nutty: "مكسرات", spice: "بهارات",
  caramel_sweet: "حلو فيه كراميل", chocolate: "شوكولاتة", tea: "شاي",
};

export const PROFILE_COLOR = {
  juicy_fruity: FAMILY_COLOR.fruity,
  citrus: FAMILY_COLOR.citrus,
  floral: FAMILY_COLOR.floral,
  sweet_caramel: FAMILY_COLOR.caramel_sweet,
  fruity_chocolate: "#B0563F",
  chocolate_nutty: FAMILY_COLOR.chocolate,
};

// chart series: ours, keyword search, random baseline
export const SERIES = { ours: "#4E9A6B", keyword: "#C9A227", baseline: "#8C8A83" };

export const REASONS = {
  same_body: "نفس القوام", same_acidity: "نفس مستوى الحموضة", same_bitterness: "نفس مستوى المرارة", similar_flavor: "نكهات قريبة",
  matches_flavor: "فيه النكهة اللي طلبتها", same_origin: "نفس بلد المنشأ", same_process: "نفس طريقة المعالجة",
  similar_price: "سعر قريب", cheaper: "أرخص من المحصول اللي اخترته", within_budget: "ضمن ميزانيتك",
  suits_brew: "يناسب طريقة تحضيرك", in_profile: "من نفس شخصية القهوة",
};

const MAPS = {
  process: {
    Natural: "مجففة", Washed: "مغسولة", Anaerobic: "لاهوائية", Honey: "عسلية", Mixed: "مختلطة", Infused: "منكهة",
    "Experimental Fermentation": "تخمير تجريبي", Decaf: "منزوعة الكافيين", Other: "أخرى",
  },
  country: {
    Ethiopia: "إثيوبيا", Colombia: "كولومبيا", Brazil: "البرازيل", Yemen: "اليمن", "Saudi Arabia": "السعودية",
    Kenya: "كينيا", Uganda: "أوغندا", Rwanda: "رواندا", "El Salvador": "السلفادور", "Costa Rica": "كوستاريكا",
    Panama: "بنما", Indonesia: "إندونيسيا", Guatemala: "غواتيمالا", Peru: "بيرو", Honduras: "هندوراس", India: "الهند",
    Nicaragua: "نيكاراغوا", Ecuador: "الإكوادور", China: "الصين", Myanmar: "ميانمار",
    "Papua New Guinea": "بابوا غينيا الجديدة", Multiple: "عدة دول",
  },
  level: { Light: "خفيف", Medium: "متوسط", Full: "ثقيل", Low: "قليلة", High: "عالية" },
  acidity: { Low: "قليلة", Medium: "متوسطة", High: "عالية" },
  city: {
    Riyadh: "الرياض", Jeddah: "جدة", Khobar: "الخبر", Dammam: "الدمام", Madinah: "المدينة", Buraydah: "بريدة",
    Qassim: "القصيم", "Al Majma'ah": "المجمعة", Tabuk: "تبوك", Safwa: "صفوى", Yanbu: "ينبع", Makkah: "مكة",
    "Al-Kharj": "الخرج", "Central Region": "المنطقة الوسطى",
  },
  brew: { espresso: "إسبريسو", filter: "فلتر" },
};

// translate a value from the data (always English) to Arabic; unknown values are hidden
export function ar(kind, value) {
  if (value == null) return null;
  return MAPS[kind][value] || null;
}

export const TEAM = [
  { name: "ربى العتيبي" },
  { name: "رغد الأسمري" },
  { name: "دانية العيد" },
  { name: "عمر الشعيل" },
];

export const REPO_URL = "https://github.com/Raghad0za/Machine-Learning-Final-Project";

// numbers: always western digits, with thousands separators
export const num = (v) => Number(v).toLocaleString("en-US");
export const pct = (v) => `${Math.round(v * 100)}٪`;
