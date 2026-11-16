# recommender.py: the real Coffee Matchmaker recommender.
# Same 5 functions and the same response shape as the mock in the handoff doc.
# Runtime needs only numpy (+ rapidfuzz if installed). Everything is loaded once at import.
#
# How it works:
#   1. Understand the request (Arabic or English): flavors, budget, brew method, body, acidity,
#      process, origin, decaf, Saudi coffee, and "something like <coffee>".
#   2. Apply hard filters (in stock, budget, brew method, ...).
#   3. K-Nearest Neighbors: the request becomes a vector in the same feature space as the coffees
#      (built and saved by the notebook, section 27), and we rank coffees by cosine similarity.
#   4. Return the top_k with reasons, keeping max 2 coffees per roaster.

import csv
import json
import math
import re
from pathlib import Path
from urllib.parse import quote

import numpy as np

try:
    from rapidfuzz import fuzz
except ImportError:  # small fallback so the app still runs without rapidfuzz
    from difflib import SequenceMatcher

    class fuzz:  # noqa: N801
        @staticmethod
        def ratio(a, b):
            return 100 * SequenceMatcher(None, a, b).ratio()

        @staticmethod
        def partial_ratio(a, b):
            if not a or not b:
                return 0
            short, long_ = (a, b) if len(a) <= len(b) else (b, a)
            best = 0
            for i in range(len(long_) - len(short) + 1):
                best = max(best, SequenceMatcher(None, short, long_[i:i + len(short)]).ratio())
            return 100 * best


ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "app_coffees.csv"
PROFILES_PATH = ROOT / "models" / "profiles.json"
LEXICON_PATH = ROOT / "models" / "lexicon.json"

FAMILIES = ["fruity", "citrus", "floral", "chocolate", "nutty", "caramel_sweet", "spice", "tea"]

# Chosen in the notebook (section 27.1, "twin test"): notes matter more than broad families.
INDEX_PATH = ROOT / "models" / "knn_index.npz"
META_PATH = ROOT / "models" / "knn_meta.json"
MIN_SCORE = 0.45  # weaker matches are not shown (unless nothing else is left)

# ----------------------------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------------------------

_AR_MARKS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_CHAR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٫": ".", "’": "'", "‘": "'",
})
_AR_PREFIXES = ["وبال", "وال", "بال", "فال", "كال", "لل", "ال", "و", "ب", "ل", "ف", "ك"]


def normalize(text):
    """Lowercase, remove Arabic diacritics, unify letter shapes and digits, drop punctuation."""
    text = _AR_MARKS.sub("", str(text).lower()).translate(_CHAR_MAP)
    text = re.sub(r"(\d)\.(\d)", r"\1<dot>\2", text)
    text = re.sub(r"[^\w\s]", " ", text).replace("<dot>", ".").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _is_arabic(token):
    return any("؀" <= ch <= "ۿ" for ch in token)


def _strip_al(token):
    return token[2:] if token.startswith("ال") and len(token) >= 4 else token


def token_variants(token):
    """All the forms a query word could match: 'والفراوله' -> {'فراوله', ...}, 'berries' -> {'berry', ...}."""
    out = {token}
    if _is_arabic(token):
        for prefix in _AR_PREFIXES:
            if token.startswith(prefix) and len(token) - len(prefix) >= 2:
                out.add(token[len(prefix):])
        out |= {_strip_al(v) for v in list(out)}
    else:
        if token.endswith("'s"):
            token = token[:-2]
            out.add(token)
        if token.endswith("ies") and len(token) > 4:
            out.add(token[:-3] + "y")
        if token.endswith("es") and len(token) > 3:
            out.add(token[:-2])
        if token.endswith("s") and len(token) > 3:
            out.add(token[:-1])
    return out


def _canonical_tokens(phrase):
    tokens = normalize(phrase).split()
    return tuple(_strip_al(t) if _is_arabic(t) else _singular(t) for t in tokens)


def _singular(token):
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


# When two words of the same length match the same spot, the broader meaning wins
# (e.g. "chocolate" = the chocolate family, not only the single note "Chocolate").
KIND_PRIORITY = {"family": 0, "region": 2, "note": 3}


class PhraseMatcher:
    """Finds the longest known phrases in a query, without overlaps."""

    def __init__(self):
        self.by_first = {}
        self.single_words = {}  # one-word English flavor terms, for typos

    def add(self, phrase, kind, value):
        tokens = _canonical_tokens(phrase)
        if tokens:
            self.by_first.setdefault(tokens[0], []).append((tokens, kind, value))
            if kind in ("family", "note") and len(tokens) == 1 and tokens[0].isascii() and len(tokens[0]) >= 5:
                self.single_words.setdefault(tokens[0], (kind, value))

    def find(self, variants):
        found = []
        for i, first_variants in enumerate(variants):
            for v in first_variants:
                for tokens, kind, value in self.by_first.get(v, []):
                    n = len(tokens)
                    if i + n <= len(variants) and all(tokens[j] in variants[i + j] for j in range(1, n)):
                        found.append((i, n, kind, value))
        # small English typos ("fruty", "choclate"): a word nobody matched is compared with the one-word flavor terms
        covered = {i + k for i, n, _, _ in found for k in range(n)}
        for i, first_variants in enumerate(variants):
            word = min(first_variants, key=len) if first_variants else ""
            if i in covered or len(word) < 5 or not word.isascii() or not word.isalpha():
                continue
            best = None
            for w, (kind, value) in self.single_words.items():
                score = fuzz.ratio(word, w)
                if score >= 85 and abs(len(word) - len(w)) <= 2 and (best is None or score > best[0]):
                    best = (score, kind, value)
            if best:
                found.append((i, 1, best[1], best[2]))
        found.sort(key=lambda m: (-m[1], m[0], KIND_PRIORITY.get(m[2], 1)))
        used, result = set(), []
        for i, n, kind, value in found:
            span = set(range(i, i + n))
            if span & used:
                continue
            used |= span
            result.append((i, n, kind, value))
        return sorted(result)


# ----------------------------------------------------------------------------------------
# Hand-written vocabulary (Arabic + English). Data-driven words come from models/lexicon.json.
# ----------------------------------------------------------------------------------------

FAMILY_WORDS = {
    "fruity": ["فواكه", "فواكهي", "فواكهيه", "فاكهي", "فاكهيه", "فاكهه", "فاكهة", "فروتي", "فروتيه", "توتي",
               "fruity", "fruit", "fruits", "fruitiness", "juicy", "عصيري"],
    "citrus": ["حمضيات", "حمضي", "حمضيه", "ليموني", "citrus", "citrusy", "citric", "zesty", "منعش", "منعشه", "refreshing"],
    "floral": ["زهري", "زهريه", "زهور", "ازهار", "وردي", "floral", "flowery", "flower", "flowers"],
    "chocolate": ["شوكولاته", "شوكولاتي", "شوكلت", "شوكولا", "شكولاته", "كاكاو", "chocolate", "chocolatey",
                  "chocolaty", "choco", "cocoa", "cacao"],
    "nutty": ["مكسرات", "nutty", "nuts", "nut"],
    "caramel_sweet": ["حلو", "حلوه", "حلاوه", "سكري", "كراميل", "كاراميل", "sweet", "sweetness", "caramel",
                      "caramelly", "sugary"],
    "spice": ["بهارات", "توابل", "متبل", "spice", "spices", "spicy"],
    "tea": ["شاي", "شايي", "tea", "tea like", "tealike"],
}

# Keyword rules that give each tasting note its flavor families (used for notes in queries).
NOTE_FAMILY_RULES = {
    "fruity": ["berr", "fruit", "strawberr", "peach", "grape", "cherr", "apricot", "pineapple", "mango", "passion",
               "apple", "raisin", "fig", "plum", "melon", "kiwi", "banana", "guava", "lychee", "papaya", "pomegranate",
               "currant", "raspberr", "blackberr", "cranberr", "date", "tutti", "pear", "nectarine", "coconut",
               "wine", "jam", "jaljal", "frutti", "cantaloupe", "olive", "fruity"],
    "citrus": ["citrus", "orange", "lemon", "lime", "grapefruit", "tangerine", "mandarin", "bergamot", "pomelo",
               "citric", "zest", "yuzu"],
    "floral": ["floral", "flower", "jasmine", "rose", "lavender", "hibiscus", "chamomile", "violet", "blossom",
               "aromatic"],
    "chocolate": ["chocolate", "cocoa", "cacao", "choco", "nib", "tiramisu"],
    "nutty": ["hazelnut", "almond", "walnut", "pecan", "peanut", "cashew", "macadamia", "pistachio",
              "sesame", "praline"],
    "caramel_sweet": ["caramel", "sugar", "honey", "toffee", "molasses", "vanilla", "sweet", "candy", "syrup", "fudge",
                      "nougat", "panela", "maple", "cream", "milkshake", "wafer", "gum", "beeswax", "cotton"],
    "spice": ["spice", "cinnamon", "clove", "nutmeg", "pepper", "cardamom", "thyme", "basil", "mint", "saffron"],
    "tea": ["tea"],
}

BREW_WORDS = {
    "filter": ["v60", "في 60", "في60", "فلتر", "فلترات", "مقطره", "مقطر", "تقطير", "دريب", "drip", "pour over",
               "pourover", "filter", "chemex", "كيمكس", "aeropress", "ايروبرس", "french press", "فرنش برس", "كاليتا",
               "kalita", "cold brew", "كولد برو", "اوريغامي", "origami", "هاريو", "hario"],
    "espresso": ["espresso", "اسبريسو", "اسبرسو", "اسبريسسو", "اسبرسسو", "latte", "lattes", "لاتيه", "لاتيه", "لاتي",
                 "cappuccino", "كابتشينو", "كابوتشينو", "كابتشينو", "flat white", "فلات وايت", "cortado", "كورتادو",
                 "milk", "حليب", "بالحليب", "piccolo", "بيكولو", "moka", "موكا", "مكينه", "machine", "spanish latte",
                 "سبانش"],
}

BODY_WORDS = {
    "Full": ["قوام ثقيل", "قوام ممتلي", "قوام عالي", "قوام قوي", "قوام كثيف", "ثقيل", "ثقيله", "full body",
             "full bodied", "heavy body", "heavy", "rich body", "thick", "syrupy"],
    "Medium": ["قوام متوسط", "medium body", "medium bodied"],
    "Light": ["قوام خفيف", "light body", "light bodied", "خفيف", "خفيفه", "delicate", "tea like body"],
}

ACIDITY_WORDS = {
    "High": ["حموضه عاليه", "حموضه واضحه", "حموضه قويه", "حموضه حلوه", "حامض", "حامضه", "high acidity",
             "high acid", "acidic", "bright", "tangy", "lively", "vibrant", "sour"],
    "Medium": ["حموضه متوسطه", "حموضه معتدله", "medium acidity", "balanced acidity"],
    "Low": ["بدون حموضه", "بلا حموضه", "حموضه قليله", "حموضه خفيفه", "حموضه منخفضه", "حموضه اقل", "قليل الحموضه",
            "قليله الحموضه", "ما فيها حموضه", "مافيها حموضه", "low acidity", "low acid", "no acidity", "less acidic",
            "not acidic", "less acidity", "mellow"],
}
BITTERNESS_WORDS = {
    "High": ["مراره عاليه", "مراره قويه", "مراره واضحه", "مراره كثير", "مره عاليه", "قهوه قويه", "قويه", "قوي",
             "high bitterness", "very bitter", "bitter", "strong bitterness", "strong coffee", "strong", "bold"],
    "Medium": ["مراره متوسطه", "مراره معتدله", "medium bitterness", "balanced bitterness"],
    "Low": ["بدون مراره", "بلا مراره", "مراره قليله", "مراره خفيفه", "مراره منخفضه", "مراره اقل", "قليل المراره",
            "قليله المراره", "ما فيها مراره", "مافيها مراره", "low bitterness", "less bitter", "not bitter",
            "no bitterness", "little bitterness", "not too bitter"],
}
# "حموضته قليلة" / "حموضتها عالية": the same phrases with "its"
for _level, _words in ACIDITY_WORDS.items():
    _words += [w.replace("حموضه", form) for w in list(_words) if w.startswith("حموضه") for form in ("حموضته", "حموضتها")]
for _level, _words in BITTERNESS_WORDS.items():
    _words += [w.replace("مراره", form) for w in list(_words) if w.startswith("مراره") for form in ("مرارته", "مرارتها")]

PROCESS_WORDS = {
    "Natural": ["مجففه", "مجفف", "ناتشورال", "ناتشرال", "طبيعيه المعالجه", "natural process", "natural", "naturals",
                "dry process"],
    "Washed": ["مغسوله", "مغسول", "washed", "wet process"],
    "Anaerobic": ["لاهوائي", "لاهوائيه", "لا هوائي", "لا هوائيه", "انيروبك", "انيروبيك", "anaerobic"],
    "Honey": ["معالجه عسليه", "عسليه المعالجه", "honey process", "honey processed", "عسليه"],
}

COUNTRY_WORDS = {
    "Ethiopia": ["اثيوبيا", "اثيوبي", "اثيوبيه", "حبشي", "ethiopia", "ethiopian"],
    "Colombia": ["كولومبيا", "كولومبي", "كولومبيه", "كولمبيا", "colombia", "colombian", "columbia", "columbian"],
    "Brazil": ["برازيل", "برازيلي", "برازيليه", "brazil", "brazilian"],
    "Yemen": ["يمن", "يمني", "يمنيه", "yemen", "yemeni"],
    "Saudi Arabia": ["سعودي", "سعوديه", "محصول سعودي", "جازان", "جيزان", "saudi", "jazan", "jizan"],
    "Kenya": ["كينيا", "كيني", "كينيه", "kenya", "kenyan"],
    "Uganda": ["اوغندا", "اوغندي", "اوغنديه", "يوغندا", "uganda", "ugandan"],
    "Rwanda": ["رواندا", "رواندي", "rwanda", "rwandan"],
    "El Salvador": ["سلفادور", "سلفادوري", "el salvador", "salvador", "salvadoran"],
    "Costa Rica": ["كوستاريكا", "كوستا ريكا", "costa rica", "costa rican"],
    "Panama": ["بنما", "بنمي", "panama", "panamanian"],
    "Indonesia": ["اندونيسيا", "اندونيسي", "اندونيسيه", "اندنوسيا", "indonesia", "indonesian", "sumatra", "java", "bali"],
    "Guatemala": ["غواتيمالا", "جواتيمالا", "guatemala", "guatemalan"],
    "Peru": ["بيرو", "peru", "peruvian"],
    "Honduras": ["هندوراس", "honduras"],
    "India": ["هند", "هندي", "هنديه", "india", "indian"],
    "Nicaragua": ["نيكاراغوا", "nicaragua"],
    "Ecuador": ["اكوادور", "ecuador"],
    "China": ["صين", "صيني", "صينيه", "china", "chinese", "yunnan"],
    "Kenya ": [],
}
COUNTRY_WORDS.pop("Kenya ")

COUNTRY_AR = {"Ethiopia": "اثيوبيا", "Colombia": "كولومبيا", "Brazil": "البرازيل", "Yemen": "اليمن",
              "Saudi Arabia": "السعودية", "Kenya": "كينيا", "Uganda": "اوغندا", "Rwanda": "رواندا",
              "El Salvador": "السلفادور", "Costa Rica": "كوستاريكا", "Panama": "بنما", "Indonesia": "اندونيسيا",
              "Guatemala": "غواتيمالا", "Peru": "بيرو", "Honduras": "هندوراس", "India": "الهند",
              "Nicaragua": "نيكاراغوا", "Ecuador": "الاكوادور", "China": "الصين", "Myanmar": "ميانمار",
              "Papua New Guinea": "بابوا غينيا الجديدة", "Multiple": "عدة دول"}

DECAF_WORDS = ["ديكاف", "منزوع الكافيين", "منزوعه الكافيين", "بدون كافيين", "خالي من الكافيين", "خاليه من الكافيين",
               "decaf", "decaffeinated", "caffeine free", "no caffeine", "without caffeine"]
SAUDI_COFFEE_WORDS = ["قهوه سعوديه", "قهوه عربيه", "هيل", "زعفران", "قهوه شقرا", "saudi coffee", "arabic coffee",
                      "arabian coffee", "cardamom", "saffron", "gahwa", "qahwa"]
EXCLUDE_INFUSED_WORDS = ["بدون نكهات مضافه", "بدون نكهه مضافه", "بدون منكهات", "بدون منكه", "مو منكهه", "غير منكهه",
                         "مب منكهه", "ما ابي منكهه", "بدون انفيوجن", "no infused", "not infused", "without infused",
                         "no infusion", "no added flavor", "no added flavors", "no added flavour", "no flavored",
                         "not flavored", "nothing infused", "no flavoured"]
INCLUDE_INFUSED_WORDS = ["منكهه", "منكه", "انفيوجن", "انفيوزد", "infused", "infusion", "flavored", "flavoured"]
CHEAP_WORDS = ["رخيص", "رخيصه", "ارخص", "اقتصادي", "اقتصاديه", "cheap", "cheaper", "cheapest", "budget friendly",
               "affordable", "inexpensive", "على قد الحال"]
NEGATION_WORDS = {"بدون", "بلا", "مو", "مب", "غير", "without", "no", "not", "dont", "don't", "avoid", "except", "ولا"}

FOCUS_WORDS = {
    "body": ["قوام", "قوامه", "القوام", "body", "mouthfeel", "texture"],
    "acidity": ["حموضه", "حموضته", "acidity", "acid"],
    "bitterness": ["مراره", "مرارته", "bitterness"],
    "flavor": ["نكهه", "نكهات", "نكهته", "طعم", "طعمه", "flavor", "flavour", "flavors", "taste", "notes"],
    "price": ["سعر", "سعره", "ارخص", "رخيص", "price", "cheaper", "cheap", "budget"],
    "origin": ["منشا", "بلد", "مصدر", "origin", "country"],
    "process": ["معالجه", "معالجته", "process", "processing"],
}
REFERENCE_CUES = ["يشبه", "تشبه", "يشبهه", "يشابه", "شبيه", "شبه", "زي", "مثل", "قريب من", "نفس", "اعجبني",
                  "عجبني", "عجبتني", "اعجبتني", "حبيت", "جربت", "بديل", "like", "similar to", "similar", "liked",
                  "loved", "same as", "alternative to", "close to", "enjoyed"]
REFERENCE_STOP = {"وش", "ايش", "شو", "what", "whats", "but", "بس", "with", "under", "below", "for", "عشان",
                  "علشان", "تحت", "اقل", "budget", "less", "cheaper", "ارخص", "وابي", "and", "و"}
NAME_STOPWORDS = {"من", "في", "حق", "حقت", "حقه", "اللي", "الي", "هذا", "هذي", "قهوه", "قهوة", "محصول", "محمصه",
                  "بن", "شي", "شيء", "مع", "يا", "ابي", "ابغى", "ابغي", "ودي", "عطني", "the", "a", "an", "of", "from",
                  "coffee", "beans", "bean", "crop", "roastery", "roaster", "one", "that", "this", "something",
                  "anything", "is", "it", "its", "i", "me", "my", "please", "want", "some", "to", "kind", "type",
                  "body", "acidity", "bitterness", "flavor", "flavour", "taste", "price", "origin", "process", "قوام", "حموضه", "مراره",
                  "نكهه", "طعم", "سعر", "معالجه", "منشا", "يشبهه", "يشبه", "زيه", "مثله", "really", "lot", "so"}
SIZE_PATTERN = re.compile(r"\b\d+(\.\d+)?\s*(g|gr|gm|kg|جرام|غرام|جم|غم|ج|غ|كيلو|كجم|كغ|ك)\b")


# ----------------------------------------------------------------------------------------
# Load data (once, at import)
# ----------------------------------------------------------------------------------------

def _to_bool(value):
    return str(value).strip() in {"1", "True", "true", "1.0"}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_coffees():
    coffees = []
    with open(DATA_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            notes = [n for n in row["tasting_notes"].split("; ") if n] if row["tasting_notes"] else []
            coffees.append({
                "coffee_id": int(row["coffee_id"]),
                "coffee_name": row["coffee_name"],
                "coffee_name_ar": row["coffee_name_ar"] or None,
                "name_ar": row["coffee_name_display_ar"] or row["coffee_name"],
                "roaster": row["roaster"],
                "roaster_ar": row["roaster_ar"] or row["roaster"],
                "region_ar": row["region_ar"] or None,
                "roaster_city": row["roaster_city"] or None,
                "origin_country": row["origin_country"] or None,
                "origin_continent": row["origin_continent"] or None,
                "region": row["region"] or None,
                "process": row["process"] or None,
                "product_type": row["product_type"],
                "is_infused": _to_bool(row["is_infused"]),
                "is_spiced": _to_bool(row["is_spiced"]),
                "price_sar": float(row["price_sar"]),
                "weight_g": int(float(row["weight_g"])),
                "price_per_100g_sar": float(row["price_per_100g_sar"]),
                "price_is_estimated": _to_bool(row["price_is_estimated"]),
                "body_level": row["body_level"] or None,
                "body_is_predicted": _to_bool(row["body_is_predicted"]),
                "body_confidence": _to_float(row["body_confidence"]),
                "acidity_level": row["acidity_level"] or None,
                "acidity_score": float(row["acidity_score"]),
                "acidity_is_estimated": _to_bool(row["acidity_is_estimated"]),
                "bitterness_level": row["bitterness_level"] or None,
                "bitterness_is_estimated": _to_bool(row["bitterness_is_estimated"]),
                "tasting_notes": notes,
                "tasting_notes_are_predicted": _to_bool(row["tasting_notes_are_predicted"]),
                "families": [f for f in FAMILIES if _to_bool(row[f])],
                "suits_espresso": _to_bool(row["suits_espresso"]),
                "suits_filter": _to_bool(row["suits_filter"]),
                "out_of_stock": _to_bool(row["out_of_stock"]),
                "profile_id": int(row["profile_id"]),
                "product_url": quote(row["product_url"], safe=":/?#[]@!$&'()*+,;=%-._~"),
            })
    return coffees


COFFEES = _load_coffees()
BY_ID = {c["coffee_id"]: i for i, c in enumerate(COFFEES)}
N = len(COFFEES)

with open(PROFILES_PATH, encoding="utf-8") as f:
    PROFILES = json.load(f)
PROFILE_BY_ID = {p["profile_id"]: p for p in PROFILES}

with open(LEXICON_PATH, encoding="utf-8") as f:
    LEXICON = json.load(f)

# --- the KNN feature space, built and saved by the notebook (section 27) ---
with open(META_PATH, encoding="utf-8") as f:
    KNN_META = json.load(f)
_index = np.load(INDEX_PATH)
assert [int(x) for x in _index["coffee_id"]] == [c["coffee_id"] for c in COFFEES], "knn index and data don't match"
X = _index["X"].astype(float)
BLOCK_NAMES = list(KNN_META["blocks"])
BLOCKS = {b: slice(*KNN_META["blocks"][b]) for b in BLOCK_NAMES}
XB = {b: X[:, BLOCKS[b]] for b in BLOCK_NAMES}   # every block of every coffee has length 1
WEIGHTS = dict(KNN_META["weights"])              # the notebook tunes these (section 28)
FOCUS_FACTOR = float(KNN_META["focus_factor"])    # "I liked its body" multiplies the body weight by this

NOTE_VOCAB = KNN_META["note_vocab"]
NOTE_INDEX = {n: i for i, n in enumerate(NOTE_VOCAB)}
IDF = np.array(KNN_META["idf"])
FOCUS_BLOCKS = {"flavor": ["notes", "families"], "body": ["body"], "acidity": ["acidity"], "bitterness": ["bitterness"], "process": ["process"],
                "origin": ["origin"], "price": ["price"]}


def _l2(matrix):
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


def _note_vector(notes):
    v = np.zeros(len(NOTE_VOCAB))
    for n in notes:
        if n in NOTE_INDEX:
            v[NOTE_INDEX[n]] += 1
    return _l2(v * IDF)


def _family_vector(families):
    return _l2(np.array([1.0 if f in families else 0.0 for f in FAMILIES]))


FAM = np.array([[1.0 if f in c["families"] else 0.0 for f in FAMILIES] for c in COFFEES])
LOG_P100 = np.log(np.array([c["price_per_100g_sar"] for c in COFFEES]))
IN_STOCK = np.array([not c["out_of_stock"] for c in COFFEES])


def _one_hot(block, name, names):
    v = np.zeros(BLOCKS[block].stop - BLOCKS[block].start)
    if name in names:
        v[names.index(name)] = 1.0
    return v


def request_blocks(u):
    """Turns an understood request into vectors, only for the blocks the user talked about."""
    q = {}
    notes = [n for n in (u.get("notes") or []) if n in NOTE_INDEX]
    if notes:
        q["notes"] = _note_vector(notes)
    if u.get("flavors"):
        q["families"] = _family_vector(u["flavors"])
    if u.get("body") in KNN_META["body_names"]:
        q["body"] = _one_hot("body", u["body"], KNN_META["body_names"])
    if u.get("acidity") in KNN_META["acidity_names"]:
        q["acidity"] = _one_hot("acidity", u["acidity"], KNN_META["acidity_names"])
    if u.get("bitterness") in KNN_META.get("bitterness_names", []):
        q["bitterness"] = _one_hot("bitterness", u["bitterness"], KNN_META["bitterness_names"])
    if u.get("process") in KNN_META["process_names"]:
        q["process"] = _one_hot("process", u["process"], KNN_META["process_names"])
    if u.get("region") in KNN_META["region_names"]:
        countries, regions = KNN_META["country_names"], KNN_META["region_names"]
        v = np.zeros(len(countries) + len(regions))
        if u.get("origin") in countries:
            v[countries.index(u["origin"])] = 1.0
        v[len(countries) + regions.index(u["region"])] = 1.0
        q["origin"] = _l2(v)
    if u.get("cheap"):
        q["price"] = _one_hot("price", "cheap", KNN_META["price_names"])
    return q


def similarity_to_request(q, idx=None, weights=None):
    """Cosine similarity between the request and the coffees, on the blocks the request has.
    Every block has length 1, so this is the weighted average of each block's similarity,
    and it gives the same order as scikit-learn's NearestNeighbors(metric="cosine") (checked in the notebook)."""
    w = weights or WEIGHTS
    rows = slice(None) if idx is None else np.asarray(list(idx), dtype=int)
    per_block = {b: XB[b][rows] @ v for b, v in q.items()}
    total = sum(w[b] for b in q)
    score = sum(w[b] * per_block[b] for b in q) / total
    return score, per_block


def focus_weights(focus):
    w = dict(WEIGHTS)
    for b in FOCUS_BLOCKS.get(focus, []):
        w[b] *= FOCUS_FACTOR
    return w


def similarity_to_coffee(r, focus="overall", idx=None):
    """KNN with a coffee as the query: all 7 blocks, the focus block counts more."""
    q = {b: XB[b][r] for b in BLOCK_NAMES}
    return similarity_to_request(q, idx, focus_weights(focus))


# --- families of every known note (for notes the user types) ---
NOTE_FAMILIES = {}
for note in set(NOTE_VOCAB) | set(LEXICON["note_ar"].values()) | set(LEXICON["note_en"].values()):
    low = note.lower()
    NOTE_FAMILIES[note] = [fam for fam, keys in NOTE_FAMILY_RULES.items()
                           if any(k in low for k in keys) or (fam == "nutty" and set(low.split()) & {"nut", "nuts"})]

NOTE_AR = LEXICON["note_display_ar"]  # English note -> Arabic, for Arabic messages and cards
REGION_AR = {}
for _ar, _en in LEXICON["region_ar"].items():
    if _en not in REGION_AR or len(_ar) < len(REGION_AR[_en]):
        REGION_AR[_en] = _ar
for _c in COFFEES:
    if _c["region"] and _c["region_ar"]:
        REGION_AR.setdefault(_c["region"], _c["region_ar"])

# --- the phrase matcher with every word we understand ---
MATCHER = PhraseMatcher()
for fam, words in FAMILY_WORDS.items():
    for w in words:
        MATCHER.add(w, "family", fam)
for ar, en in LEXICON["note_ar"].items():
    MATCHER.add(ar, "note", en)
for raw, en in LEXICON["note_en"].items():
    MATCHER.add(raw, "note", en)
for note in NOTE_VOCAB:
    MATCHER.add(note, "note", note)
for brew, words in BREW_WORDS.items():
    for w in words:
        MATCHER.add(w, "brew", brew)
for level, words in BODY_WORDS.items():
    for w in words:
        MATCHER.add(w, "body", level)
for level, words in ACIDITY_WORDS.items():
    for w in words:
        MATCHER.add(w, "acidity", level)
for level, words in BITTERNESS_WORDS.items():
    for w in words:
        MATCHER.add(w, "bitterness", level)
for proc, words in PROCESS_WORDS.items():
    for w in words:
        MATCHER.add(w, "process", proc)
for country, words in COUNTRY_WORDS.items():
    for w in words:
        MATCHER.add(w, "country", country)
for ar, en in LEXICON["region_ar"].items():
    MATCHER.add(ar, "region", en)
for region in {c["region"] for c in COFFEES if c["region"] and c["region"] not in {"Unknown", "Multiple"}}:
    if len(region) >= 4:
        MATCHER.add(region, "region", region)
for w in DECAF_WORDS:
    MATCHER.add(w, "decaf", True)
for w in SAUDI_COFFEE_WORDS:
    MATCHER.add(w, "saudi_coffee", True)
for w in EXCLUDE_INFUSED_WORDS:
    MATCHER.add(w, "infused", "exclude")
for w in INCLUDE_INFUSED_WORDS:
    MATCHER.add(w, "infused", "include")
for w in CHEAP_WORDS:
    MATCHER.add(w, "cheap", True)

# Words that are names of flavors/places (a "reference" made only of these is not a coffee name).
_LEXICON_TOKENS, _FLAVOR_TOKENS = set(), set()
for tokens_list in MATCHER.by_first.values():
    for tokens, kind, _ in tokens_list:
        _LEXICON_TOKENS |= set(tokens)
        if kind in {"family", "note"}:
            _FLAVOR_TOKENS |= set(tokens)

# Arabic place words -> English (helps match "كولومبيا ويلا" to "Colombia Huila").
AR_TO_EN_WORD = {}
for country, words in COUNTRY_WORDS.items():
    for w in words:
        if _is_arabic(w) and " " not in w:
            AR_TO_EN_WORD[_strip_al(normalize(w))] = country.lower()
for ar, en in LEXICON["region_ar"].items():
    if " " not in ar.strip():
        AR_TO_EN_WORD[_strip_al(normalize(ar))] = en.lower()


def _name_key(text):
    text = SIZE_PATTERN.sub(" ", normalize(text))
    return " ".join(_strip_al(t) for t in text.split() if t not in NAME_STOPWORDS)


NAME_KEYS = []
for c in COFFEES:
    keys = [_name_key(c["coffee_name"]), _name_key(c["coffee_name"] + " " + c["roaster"])]
    keys.append(_name_key(c["name_ar"]))
    if c["coffee_name_ar"]:
        for ar_name in c["coffee_name_ar"].split(" || "):
            keys.append(_name_key(ar_name))
    NAME_KEYS.append([k for k in keys if k])


# ----------------------------------------------------------------------------------------
# 1) Understanding the request
# ----------------------------------------------------------------------------------------

def _empty_understanding():
    return {"reference_coffee_id": None, "reference_coffee_name": None, "focus": "overall", "flavors": [],
            "max_price_sar": None, "brew_method": None, "notes": [], "excluded_flavors": [], "body": None,
            "acidity": None, "bitterness": None, "process": None, "origin": None, "region": None, "decaf": False,
            "saudi_coffee": False, "exclude_infused": False, "want_infused": False, "cheap": False}


def _parse_budget(norm):
    text = re.sub(r"\bv\s?60\b|في ?60|\b\d+\s?(?:%|٪)", " ", norm)
    text = SIZE_PATTERN.sub(" ", text)
    cue = (r"(?:اقل من|اقل|تحت|ما يتعدي|مايتعدي|ما يزيد عن|ما تزيد عن|لا يتجاوز|حدود|بحدود|ميزانيتي|ميزانيه|ميزانيتي"
           r"|under|below|less than|max|maximum|up to|upto|budget|within|at most|cheaper than)")
    m = re.search(cue + r"\s*(?:من\s*|is\s*|of\s*)?(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ريال|ريالات|ر س|رس|sar|sr|riyal|riyals|rs)\b", text)
    if m:
        return float(m.group(1))
    numbers = [float(x) for x in re.findall(r"\b\d+(?:\.\d+)?\b", text)]
    if len(numbers) == 1 and 15 <= numbers[0] <= 600:
        return numbers[0]
    return None


def _find_reference(original_text):
    """Looks for 'like <coffee name>' and returns (status, candidates)."""
    clauses = re.split(r"[،,؟?.!؛;\n]| - | but | بس ", str(original_text))
    best = None
    for clause in clauses:
        tokens = normalize(clause).split()
        if not tokens:
            continue
        variants = [token_variants(t) for t in tokens]
        cue_end = None
        for cue in REFERENCE_CUES:
            cue_tokens = _canonical_tokens(cue)
            n = len(cue_tokens)
            for i in range(len(tokens) - n + 1):
                if all(cue_tokens[j] in variants[i + j] for j in range(n)):
                    cue_end = i + n if cue_end is None else min(cue_end, i + n)
        if cue_end is None:
            continue
        phrase = []
        for t in tokens[cue_end:]:
            if t in REFERENCE_STOP:
                break
            phrase.append(t)
        phrase = [t for t in phrase if t not in NAME_STOPWORDS and not SIZE_PATTERN.fullmatch(t)]
        phrase = [_strip_al(t) if _is_arabic(t) else t for t in phrase]
        phrase = [t for t in phrase if not (token_variants(t) & set(FOCUS_WORDS_FLAT))]
        if not phrase:
            continue
        # "like honey and caramel" is about flavors, not a coffee name; "like Hambela" is a place
        if all(token_variants(t) & _FLAVOR_TOKENS for t in phrase):
            continue
        if len(phrase) == 1 and token_variants(phrase[0]) & _LEXICON_TOKENS:
            continue
        candidates = match_coffee_names(" ".join(phrase))
        if candidates and (best is None or candidates[0][1] > best[0][0][1]):
            best = (candidates, phrase)
    return best if best else ([], [])


FOCUS_WORDS_FLAT = [_strip_al(normalize(w)) for words in FOCUS_WORDS.values() for w in words]


def _skeleton(token):
    """Arabic spellings of foreign names differ in long vowels (كت / كيت, هامبيلا / همبيلا)."""
    if _is_arabic(token) and len(token) >= 2:
        return token[0] + re.sub("[اويى]", "", token[1:])
    return token


def _token_match(qt, kt):
    if qt == kt:
        return True
    if _is_arabic(qt) and _is_arabic(kt) and len(_skeleton(qt)) >= 2 and _skeleton(qt) == _skeleton(kt):
        return True
    return len(qt) >= 4 and fuzz.ratio(qt, kt) >= 85


def match_coffee_names(phrase):
    """Fuzzy match a typed name against all coffee names (English + Arabic). Returns [(index, score)]."""
    norm = normalize(phrase)
    tokens = [_strip_al(t) for t in norm.split() if t not in NAME_STOPWORDS]
    if not tokens:
        return []
    english = " ".join(AR_TO_EN_WORD.get(t, t) for t in tokens)
    queries = {" ".join(tokens), english}
    scored = []
    for i, keys in enumerate(NAME_KEYS):
        best = 0
        for q in queries:
            q_tokens = q.split()
            for key in keys:
                key_tokens = key.split()
                hits = 0
                for qt in q_tokens:
                    if any(_token_match(qt, kt) for kt in key_tokens):
                        hits += 1
                cover = 100 * hits / len(q_tokens)
                joined_q, joined_k = q.replace(" ", ""), key.replace(" ", "")
                partial = fuzz.partial_ratio(joined_q, joined_k) if len(joined_q) >= 4 else 0
                score = max(cover, partial if len(joined_q) >= 5 else 0)
                if cover < 100 and len(q_tokens) >= 3 and hits >= len(q_tokens) - 1:
                    score = max(score, 90)
                best = max(best, score)
        if best >= 88:
            tie_break = max(fuzz.ratio(q, k) for q in queries for k in keys)
            scored.append((i, best, tie_break))
    scored.sort(key=lambda s: (-s[1], -s[2]))
    return [(i, s) for i, s, _ in scored]


def understand(query):
    """Turns free text (Arabic, English or mixed) into a structured request."""
    u = _empty_understanding()
    candidates, phrase = _find_reference(query)
    tokens = normalize(query).split()
    if candidates:  # the words of the coffee name are not flavors/origins of the request
        tokens = [t for t in tokens if (_strip_al(t) if _is_arabic(t) else t) not in set(phrase)]
    norm = " ".join(tokens)
    variants = [token_variants(t) for t in tokens]
    matches = MATCHER.find(variants)

    for i, n, kind, value in matches:
        negated = i > 0 and (tokens[i - 1] in NEGATION_WORDS or (i > 1 and tokens[i - 2] in {"ما", "مو", "مب"}
                                                                      and tokens[i - 1] in {"ابي", "ابغى", "احب"}))
        if kind in {"family", "note"}:
            fams = [value] if kind == "family" else NOTE_FAMILIES.get(value, [])
            if negated:
                u["excluded_flavors"] += [f for f in fams if f not in u["excluded_flavors"]]
                continue
            if kind == "note" and value not in u["notes"]:
                u["notes"].append(value)
            u["flavors"] += [f for f in fams if f not in u["flavors"]]
        elif kind == "brew":
            u["brew_method"] = value
        elif kind == "body":
            u["body"] = value
        elif kind == "acidity":
            u["acidity"] = value
        elif kind == "bitterness":
            u["bitterness"] = value
        elif kind == "process":
            u["process"] = value
        elif kind == "country":
            if value == "Saudi Arabia" and u["saudi_coffee"]:
                continue
            u["origin"] = value
        elif kind == "region":
            u["region"] = value
        elif kind == "decaf":
            u["decaf"] = True
        elif kind == "saudi_coffee":
            u["saudi_coffee"] = True
            if u["origin"] == "Saudi Arabia":
                u["origin"] = None
        elif kind == "infused":
            if value == "exclude" or negated:
                u["exclude_infused"] = True
            else:
                u["want_infused"] = True
        elif kind == "cheap":
            u["cheap"] = True

    # the Saudi-coffee words "قهوة سعودية" also contain "سعودية": keep only the product type
    if u["saudi_coffee"] and u["origin"] == "Saudi Arabia":
        u["origin"] = None
    # a region tells us its country too
    if u["region"] and not u["origin"]:
        countries = {c["origin_country"] for c in COFFEES if c["region"] == u["region"]}
        if len(countries) == 1:
            u["origin"] = countries.pop()
    u["max_price_sar"] = _parse_budget(norm)

    for focus, words in FOCUS_WORDS.items():
        if any(_strip_al(normalize(w)) in v for w in words for v in variants):
            u["focus"] = focus
            break

    u["_reference_candidates"] = candidates
    return u


# ----------------------------------------------------------------------------------------
# 2) Scoring helpers
# ----------------------------------------------------------------------------------------

def _checks(filters, u, allow_types=()):
    """The hard filters, in order. Used for the ranking and for the "how it decided" funnel."""
    filters, u = filters or {}, u or {}
    max_price = filters.get("max_price_sar") if filters.get("max_price_sar") is not None else u.get("max_price_sar")
    max_p100 = filters.get("max_price_100g")
    brew = filters.get("brew_method") or u.get("brew_method")
    no_infused = bool(filters.get("exclude_infused")) or bool(u.get("exclude_infused"))
    decaf, saudi = bool(u.get("decaf")), bool(u.get("saudi_coffee"))
    excluded = set(u.get("excluded_flavors") or [])
    origin = u.get("origin")

    def type_ok(i, c):
        if decaf:
            if c["product_type"] != "decaf" and c["process"] != "Decaf":
                return False
        elif c["product_type"] == "decaf" and "decaf" not in allow_types:
            return False
        if saudi:
            return c["product_type"] == "saudi_coffee" or c["is_spiced"]
        return not ((c["product_type"] == "saudi_coffee" or c["is_spiced"]) and "saudi_coffee" not in allow_types)

    return [
        ("stock", True, lambda i, c: IN_STOCK[i]),
        ("budget", max_price is not None, lambda i, c: c["price_sar"] <= max_price),
        ("cheaper", max_p100 is not None, lambda i, c: c["price_per_100g_sar"] <= max_p100),
        ("brew", brew in ("espresso", "filter"),
         lambda i, c: c["suits_espresso"] if brew == "espresso" else c["suits_filter"]),
        ("infused", no_infused, lambda i, c: not c["is_infused"]),
        ("only_infused", bool(u.get("want_infused")), lambda i, c: c["is_infused"]),
        ("exclude", bool(excluded), lambda i, c: not (excluded & set(c["families"]))),
        ("decaf" if decaf else ("saudi" if saudi else "type"), True, type_ok),
        ("origin", bool(origin), lambda i, c: c["origin_country"] == origin),
    ]


def _apply_filters(indices, filters, u=None, allow_types=()):
    active = [keep for _, on, keep in _checks(filters, u, allow_types) if on]
    return [i for i in indices if all(keep(i, COFFEES[i]) for keep in active)]


def _pick_diverse(scored, top_k, max_per_roaster=2):
    """Best first, but max 2 coffees from the same roaster and no near-identical names."""
    chosen, per_roaster = [], {}
    for item in scored:
        if chosen and item[1] < MIN_SCORE:
            break
        c = COFFEES[item[0]]
        if per_roaster.get(c["roaster"], 0) >= max_per_roaster:
            continue
        if any(COFFEES[j]["roaster"] == c["roaster"] and fuzz.ratio(_name_key(COFFEES[j]["coffee_name"]),
                                                                    _name_key(c["coffee_name"])) >= 90
               for j, *_ in chosen):
            continue
        chosen.append(item)
        per_roaster[c["roaster"]] = per_roaster.get(c["roaster"], 0) + 1
        if len(chosen) == top_k:
            break
    return chosen


# ----------------------------------------------------------------------------------------
# 3) Building the response
# ----------------------------------------------------------------------------------------

def _card(i, score, reasons):
    c = COFFEES[i]
    notes = c["tasting_notes"]
    return {
        "coffee_id": c["coffee_id"],
        "coffee_name": c["coffee_name"],
        "coffee_name_ar": c["name_ar"],
        "roaster": c["roaster"],
        "roaster_ar": c["roaster_ar"],
        "roaster_city": None if c["roaster_city"] in (None, "Unknown") else c["roaster_city"],
        "origin_country": None if c["origin_country"] in (None, "Unknown") else c["origin_country"],
        "process": None if c["process"] in (None, "Unknown") else c["process"],
        "price_sar": round(c["price_sar"], 2),
        "weight_g": c["weight_g"],
        "price_per_100g_sar": round(c["price_per_100g_sar"], 2),
        "price_is_estimated": c["price_is_estimated"],
        "body_level": c["body_level"],
        "body_is_predicted": c["body_is_predicted"],
        "body_confidence": round(c["body_confidence"], 2) if c["body_is_predicted"] else None,
        "acidity_level": c["acidity_level"],
        "acidity_is_estimated": c["acidity_is_estimated"],
        "bitterness_level": c["bitterness_level"],
        "bitterness_is_estimated": c["bitterness_is_estimated"],
        "tasting_notes": notes,
        "tasting_notes_ar": [NOTE_AR.get(n, n) for n in notes],
        "tasting_notes_are_predicted": c["tasting_notes_are_predicted"],
        "families": c["families"],
        "suits_espresso": c["suits_espresso"],
        "suits_filter": c["suits_filter"],
        "match_score": round(float(score), 2),
        "reasons": reasons,
        "product_url": c["product_url"],
        "profile_id": c["profile_id"],
        "region": None if c["region"] in (None, "Unknown", "Multiple") else c["region"],
        "region_ar": None if c["region"] in (None, "Unknown", "Multiple") else c["region_ar"],
    }


def _label(i, lang):
    c = COFFEES[i]
    if lang == "ar":
        return f"{c['name_ar']}، {c['roaster_ar']}"
    return f"{c['coffee_name']}, {c['roaster']}"


def _display_name(c, lang):
    return c["name_ar"] if lang == "ar" else c["coffee_name"]


def _public_understood(u):
    out = {k: v for k, v in u.items() if not k.startswith("_")}
    return out


FAMILY_TEXT = {
    "ar": {"fruity": "فاكهي", "citrus": "حمضيات", "floral": "زهري", "chocolate": "شوكولاتة", "nutty": "مكسرات",
           "caramel_sweet": "حلو وكراميل", "spice": "بهارات", "tea": "شاي"},
    "en": {"fruity": "fruity", "citrus": "citrusy", "floral": "floral", "chocolate": "chocolatey", "nutty": "nutty",
           "caramel_sweet": "sweet & caramel", "spice": "spicy", "tea": "tea-like"},
}
LEVEL_TEXT = {
    "ar": {"body": {"Full": "قوام ثقيل", "Medium": "قوام متوسط", "Light": "قوام خفيف"},
           "acidity": {"High": "حموضة عالية", "Medium": "حموضة متوسطة", "Low": "حموضة قليلة"},
           "bitterness": {"High": "مرارة عالية", "Medium": "مرارة متوسطة", "Low": "مرارة قليلة"}},
    "en": {"body": {"Full": "full body", "Medium": "medium body", "Light": "light body"},
           "acidity": {"High": "high acidity", "Medium": "medium acidity", "Low": "low acidity"},
           "bitterness": {"High": "high bitterness", "Medium": "medium bitterness", "Low": "low bitterness"}},
}
PROCESS_AR = {"Natural": "مجففة", "Washed": "مغسولة", "Anaerobic": "لاهوائية", "Honey": "عسلية",
              "Mixed": "مختلطة", "Infused": "منكهة", "Experimental Fermentation": "تخمير تجريبي",
              "Decaf": "منزوعة الكافيين", "Other": "أخرى"}
FOCUS_TEXT = {
    "ar": {"overall": "شي", "body": "قوام", "acidity": "حموضة", "bitterness": "مرارة", "flavor": "نكهات", "price": "سعر",
           "origin": "منشأ", "process": "معالجة"},
    "en": {"overall": "something", "body": "a body", "acidity": "an acidity", "bitterness": "a bitterness", "flavor": "flavors",
           "price": "a price", "origin": "an origin", "process": "a process"},
}


def _describe(u, lang):
    parts = []
    fam_text = FAMILY_TEXT[lang]
    flavors_from_notes = {f for n in u["notes"] for f in NOTE_FAMILIES.get(n, [])}
    for f in u["flavors"]:
        if f not in flavors_from_notes or not u["notes"]:
            parts.append(fam_text[f])
    if u["notes"]:
        notes = [NOTE_AR.get(n, n) for n in u["notes"]] if lang == "ar" else [n.lower() for n in u["notes"]]
        parts.append(("فيها " + " و".join(notes)) if lang == "ar" else ("with " + " & ".join(notes)))
    for f in u["excluded_flavors"]:
        parts.append(("بدون " + fam_text[f]) if lang == "ar" else ("no " + fam_text[f]))
    if u["body"]:
        parts.append(LEVEL_TEXT[lang]["body"][u["body"]])
    if u["acidity"]:
        parts.append(LEVEL_TEXT[lang]["acidity"][u["acidity"]])
    if u.get("bitterness"):
        parts.append(LEVEL_TEXT[lang]["bitterness"][u["bitterness"]])
    if u["process"]:
        parts.append(("معالجة " + PROCESS_AR.get(u["process"], u["process"])) if lang == "ar"
                     else (u["process"].lower() + " process"))
    if u["region"]:
        parts.append(("من " + REGION_AR.get(u["region"], u["region"])) if lang == "ar" else ("from " + u["region"]))
    elif u["origin"]:
        parts.append(("من " + COUNTRY_AR.get(u["origin"], u["origin"])) if lang == "ar" else ("from " + u["origin"]))
    if u["decaf"]:
        parts.append("منزوعة الكافيين" if lang == "ar" else "decaf")
    if u["saudi_coffee"]:
        parts.append("قهوة سعودية" if lang == "ar" else "Saudi coffee")
    if u["exclude_infused"]:
        parts.append("بدون نكهات مضافة" if lang == "ar" else "no infused coffees")
    if u["want_infused"]:
        parts.append("منكهة" if lang == "ar" else "infused")
    if u["brew_method"]:
        parts.append({"ar": {"filter": "للفلتر", "espresso": "للإسبريسو"},
                      "en": {"filter": "for filter", "espresso": "for espresso"}}[lang][u["brew_method"]])
    if u["max_price_sar"] is not None:
        price = f"{u['max_price_sar']:g}"
        parts.append(f"بأقل من {price} ريال" if lang == "ar" else f"under {price} SAR")
    if u["cheap"]:
        parts.append("سعر أقل" if lang == "ar" else "lower price")
    return ("، " if lang == "ar" else ", ").join(parts)


def _no_results(u, lang, relaxed_results, relaxed):
    relaxed_text = {
        "ar": {"max_price_sar": "الميزانية", "brew_method": "طريقة التحضير", "origin": "بلد المنشأ",
               "exclude_infused": "شرط بدون منكهات", "process": "المعالجة"},
        "en": {"max_price_sar": "the budget", "brew_method": "the brew method", "origin": "the origin",
               "exclude_infused": "the no-infused rule", "process": "the process"},
    }[lang]
    if relaxed_results:
        what = (" و".join(relaxed_text[r] for r in relaxed)) if lang == "ar" else (" and ".join(relaxed_text[r] for r in relaxed))
        message = (f"ما لقيت شي يطابق كل شروطك. هذي أقرب البدائل بعد ما خففت {what}:" if lang == "ar"
                   else f"Nothing matches all your conditions. Here are the closest options after relaxing {what}:")
    else:
        message = ("ما لقيت شي يطابق الشروط، جرّب ميزانية أعلى أو شروط أقل." if lang == "ar"
                   else "Nothing matches these conditions. Try a higher budget or fewer filters.")
    return {"status": "no_results", "understood": _public_understood(u), "message": message,
            "results": relaxed_results, "options": []}


def _ok(u, message, results):
    return {"status": "ok", "understood": _public_understood(u), "message": message, "results": results,
            "options": []}


# ----------------------------------------------------------------------------------------
# 4) The 5 public functions (same names and parameters as the mock)
# ----------------------------------------------------------------------------------------

def _score_query(indices, u, filters, parts_out=None):
    """KNN for a free-text request. Returns [(index, score, reasons)] best first.
    parts_out (optional dict) receives each coffee's per-block similarity, for the "how it decided" view."""
    q = request_blocks(u)
    brew = (filters or {}).get("brew_method") or u["brew_method"]
    max_price = (filters or {}).get("max_price_sar") if (filters or {}).get("max_price_sar") is not None \
        else u["max_price_sar"]
    if not indices:
        return []
    scores, per_block = similarity_to_request(q, indices)
    scored = []
    for k, i in enumerate(indices):
        c = COFFEES[i]
        reasons = []
        if u["flavors"] and set(u["flavors"]) <= set(c["families"]):
            reasons.append("matches_flavor")
        if u["body"] and c["body_level"] == u["body"]:
            reasons.append("same_body")
        if u["acidity"] and c["acidity_level"] == u["acidity"]:
            reasons.append("same_acidity")
        if u.get("bitterness") and c["bitterness_level"] == u["bitterness"]:
            reasons.append("same_bitterness")
        if u["process"] and c["process"] == u["process"]:
            reasons.append("same_process")
        if u["origin"] and c["origin_country"] == u["origin"]:
            reasons.append("same_origin")
        if max_price is not None:
            reasons.append("within_budget")
        if brew:
            reasons.append("suits_brew")
        if parts_out is not None:
            parts_out[i] = {b: float(per_block[b][k]) for b in q}
        scored.append((i, float(scores[k]), reasons))
    scored.sort(key=lambda s: (-s[1], LOG_P100[s[0]]))
    return scored


def _diverse_picks(indices, top_k):
    """When the request has no taste words: the most typical coffee of each personality."""
    by_profile = {}
    for i in indices:
        p = PROFILE_BY_ID[COFFEES[i]["profile_id"]]
        center = np.array(p["centroid"])
        sim = float(FAM[i] @ center / (np.linalg.norm(FAM[i]) * np.linalg.norm(center) + 1e-9))
        if COFFEES[i]["profile_id"] not in by_profile or sim > by_profile[COFFEES[i]["profile_id"]][1]:
            by_profile[COFFEES[i]["profile_id"]] = (i, sim)
    picks = sorted(by_profile.values(), key=lambda s: -s[1])
    return [(i, 0.5 + 0.4 * s, ["in_profile"]) for i, s in picks][:top_k]


def recommend(query, lang="ar", top_k=5, filters=None):
    filters = filters or {}
    u = understand(query)
    candidates = u.pop("_reference_candidates")

    # "something like <coffee>" -> /similar, or ask which one
    if candidates:
        top_score = candidates[0][1]
        group = [i for i, s in candidates if s >= top_score - 8]
        if len(group) == 1:
            ref = COFFEES[group[0]]
            focus = u["focus"]
            if u["cheap"] or (u["max_price_sar"] is not None and focus == "overall"):
                focus = "price" if u["cheap"] else focus
            merged = dict(filters)
            if merged.get("max_price_sar") is None and u["max_price_sar"] is not None:
                merged["max_price_sar"] = u["max_price_sar"]
            if not merged.get("brew_method") and u["brew_method"]:
                merged["brew_method"] = u["brew_method"]
            if u["exclude_infused"]:
                merged["exclude_infused"] = True
            return similar(ref["coffee_id"], focus, lang, top_k, merged, query_text=query)
        u["reference_coffee_id"] = None
        u["reference_coffee_name"] = None
        options = [{"coffee_id": COFFEES[i]["coffee_id"], "label": _label(i, lang)} for i in group[:5]]
        more = len(group) > 5
        message = ((f"لقيت {len(group)} محصول بهذا الاسم، هذي أقربها. أي واحد تقصد؟" if more
                    else "لقيت أكثر من محصول بهذا الاسم، أي واحد تقصد؟") if lang == "ar"
                   else (f"I found {len(group)} coffees with that name, here are the closest. Which one do you mean?"
                         if more else "I found more than one coffee with that name. Which one do you mean?"))
        return {"status": "clarify", "understood": _public_understood(u), "message": message, "results": [],
                "options": options}

    # the user's filters win over what they wrote
    if filters.get("max_price_sar") is not None:
        u["max_price_sar"] = filters["max_price_sar"]
    if filters.get("brew_method"):
        u["brew_method"] = filters["brew_method"]
    if filters.get("exclude_infused"):
        u["exclude_infused"] = True

    has_taste = bool(request_blocks(u))
    allow = ("decaf",) if u["decaf"] else ()
    indices = _apply_filters(range(N), {}, u, allow)

    relaxed = []
    if not indices:
        trial = dict(u)
        for key in ["max_price_sar", "brew_method", "exclude_infused", "origin"]:
            if trial.get(key):
                trial[key] = None if key != "exclude_infused" else False
                if key == "max_price_sar":
                    trial["cheap"] = True  # over budget: show the cheapest good matches first
                relaxed.append(key)
                indices = _apply_filters(range(N), {}, trial, allow)
                if indices:
                    break
        funnel, _ = _funnel(range(N), {}, u, allow)
        words = _query_words(query, u)
        if not indices:
            out = _no_results(u, lang, [], relaxed)
            out["explain"] = _explain("none", [], [], {}, {}, funnel, words, u["flavors"], u["notes"])
            return out
        out_parts = {}
        q = request_blocks(trial)
        scored = _score_query(indices, trial, {}, out_parts) if has_taste else _diverse_picks(indices, top_k)
        picks = _pick_diverse(scored, top_k)
        out = _no_results(u, lang, [_card(i, s, r) for i, s, r in picks], relaxed)
        if has_taste:
            _, removed = _funnel(range(N), {}, trial, allow)
            out["explain"] = _explain("relaxed", scored, picks, out_parts, {b: WEIGHTS[b] for b in q}, funnel, words,
                                      u["flavors"], u["notes"], similarity_to_request(q)[0], removed, range(N))
        else:
            out["explain"] = _explain("none", [], [], {}, {}, funnel, words, u["flavors"], u["notes"])
        out["explain"]["relaxed"] = relaxed
        return out

    parts_by_i, scored = {}, []
    if has_taste:
        scored = _score_query(indices, u, {}, parts_by_i)
        picks = _pick_diverse(scored, top_k)
        desc = _describe(u, lang)
        message = (f"فهمت إنك تبي: {desc}. هذي أفضل {len(picks)}:" if lang == "ar"
                   else f"Got it, you want: {desc}. Here are the top {len(picks)}:")
    else:
        brew_or_budget = [r for r in (["within_budget"] if u["max_price_sar"] is not None else [])
                          + (["suits_brew"] if u["brew_method"] else [])]
        picks = [(i, s, r + brew_or_budget) for i, s, r in _diverse_picks(indices, top_k)]
        desc = _describe(u, lang)
        if desc:
            message = (f"فهمت: {desc}. ما حددت نكهة، فهذي تشكيلة من كل شخصية قهوة:" if lang == "ar"
                       else f"Got it: {desc}. You didn't name a flavor, so here is one from each coffee personality:")
        else:
            message = ("ما فهمت نكهة معينة، فهذي تشكيلة من كل شخصية قهوة. جرّب تكتب مثلًا: فاكهي أو شوكولاتة." if lang == "ar"
                       else "I couldn't spot a flavor, so here is one coffee from each personality. Try words like fruity or chocolate.")
    out = _ok(u, message, [_card(i, s, r) for i, s, r in picks])
    funnel, removed = _funnel(range(N), {}, u, allow)
    words = _query_words(query, u)
    if has_taste:
        q = request_blocks(u)
        out["explain"] = _explain("query", scored, picks, parts_by_i, {b: WEIGHTS[b] for b in q}, funnel, words,
                                  u["flavors"], u["notes"], similarity_to_request(q)[0], removed, range(N))
    else:
        out["explain"] = _explain("diverse", [], [], {}, {}, funnel, words, u["flavors"], u["notes"])
    return out


def similar(coffee_id, focus="overall", lang="ar", top_k=5, filters=None, query_text=None):
    if coffee_id not in BY_ID:
        raise KeyError(coffee_id)
    filters = dict(filters or {})
    r = BY_ID[coffee_id]
    ref = COFFEES[r]
    focus = focus if focus == "overall" or focus in FOCUS_BLOCKS else "overall"
    if focus == "price":  # "I liked its price": the same price or cheaper
        filters["max_price_100g"] = ref["price_per_100g_sar"]
    u = _empty_understanding()
    u.update({"reference_coffee_id": ref["coffee_id"], "reference_coffee_name": _display_name(ref, lang), "focus": focus,
              "flavors": list(ref["families"]), "max_price_sar": filters.get("max_price_sar"),
              "brew_method": filters.get("brew_method"), "exclude_infused": bool(filters.get("exclude_infused"))})

    allow = tuple(t for t in ("decaf", "saudi_coffee") if ref["product_type"] == t or
                  (t == "saudi_coffee" and ref["is_spiced"]))
    pool = [i for i in range(N) if i != r and _name_key(COFFEES[i]["coffee_name"]) != _name_key(ref["coffee_name"])
            or (i != r and COFFEES[i]["roaster"] != ref["roaster"])]
    indices = _apply_filters(pool, filters, {}, allow)
    parts_by_i = {}

    def score_all(idx):
        if not idx:
            return []
        scores, per_block = similarity_to_coffee(r, focus, idx)
        out = []
        for k, i in enumerate(idx):
            c = COFFEES[i]
            parts_by_i[i] = {b: float(per_block[b][k]) for b in BLOCK_NAMES}
            reasons = []
            shared = len(set(ref["families"]) & set(c["families"]))
            if per_block["notes"][k] >= 0.35 or shared >= 2:
                reasons.append("similar_flavor")
            if ref["body_level"] and c["body_level"] == ref["body_level"]:
                reasons.append("same_body")
            if ref["acidity_level"] and c["acidity_level"] == ref["acidity_level"]:
                reasons.append("same_acidity")
            if ref["bitterness_level"] and c["bitterness_level"] == ref["bitterness_level"]:
                reasons.append("same_bitterness")
            if ref["origin_country"] not in (None, "Unknown", "Multiple") and c["origin_country"] == ref["origin_country"]:
                reasons.append("same_origin")
            if ref["process"] not in (None, "Unknown") and c["process"] == ref["process"]:
                reasons.append("same_process")
            if c["price_per_100g_sar"] < 0.9 * ref["price_per_100g_sar"]:
                reasons.append("cheaper")
            elif abs(LOG_P100[i] - LOG_P100[r]) <= 0.2:
                reasons.append("similar_price")
            if filters.get("max_price_sar") is not None:
                reasons.append("within_budget")
            if filters.get("brew_method"):
                reasons.append("suits_brew")
            first = {"body": "same_body", "acidity": "same_acidity", "bitterness": "same_bitterness", "flavor": "similar_flavor",
                     "origin": "same_origin", "process": "same_process", "price": "cheaper"}.get(focus)
            if first in reasons:
                reasons.remove(first)
                reasons.insert(0, first)
            out.append((i, float(scores[k]), reasons[:4]))
        out.sort(key=lambda s: (-s[1], LOG_P100[s[0]]))
        return out

    if not indices:
        relaxed = []
        trial = dict(filters)
        for key in ["max_price_100g", "max_price_sar", "brew_method", "exclude_infused"]:
            if trial.get(key):
                trial[key] = None if key != "exclude_infused" else False
                relaxed.append(key)
                indices = _apply_filters(pool, trial, {}, allow)
                if indices:
                    break
        picks = _pick_diverse(score_all(indices), top_k) if indices else []
        return _no_results(u, lang, [_card(i, s, rs) for i, s, rs in picks], relaxed)

    scored = score_all(indices)
    picks = _pick_diverse(scored, top_k)
    name = _display_name(ref, lang)
    if focus == "overall":
        message = (f"هذي أقرب {len(picks)} محاصيل لـ {name}:" if lang == "ar"
                   else f"The {len(picks)} closest coffees to {name}:")
    elif focus == "price":
        message = (f"فهمت إنك تبي شي قريب من {name} بسعر أقل أو نفسه. هذي أفضل {len(picks)}:" if lang == "ar"
                   else f"Got it: something like {name} for the same price or less. Top {len(picks)}:")
    else:
        phrase = {"body": "قوام قريب من", "acidity": "حموضة قريبة من", "bitterness": "مرارة قريبة من", "flavor": "نكهات قريبة من",
                  "origin": "قهوة من نفس منشأ", "process": "قهوة بنفس طريقة معالجة"}.get(focus, "شي قريب من")
        message = (f"فهمت إنك تبي {phrase} {name}. هذي أقرب {len(picks)}:" if lang == "ar"
                   else f"Got it: {FOCUS_TEXT['en'][focus]} close to {name}. The {len(picks)} closest:")
        if focus == "body" and ref["body_level"] is None:
            message += (" (قوامه مو مكتوب، فاعتمدنا على القوام المتوقع)" if lang == "ar"
                        else " (its body isn't listed, so the predicted body was used)")
    out = _ok(u, message, [_card(i, s, rs) for i, s, rs in picks])
    all_scores, _ = similarity_to_coffee(r, focus)
    funnel, removed = _funnel(pool, filters, {}, allow)
    out["explain"] = _explain("similar", scored, picks, parts_by_i, focus_weights(focus), funnel,
                              _query_words(query_text, u, ref_phrase_ids=r) if query_text else [],
                              list(ref["families"]), list(ref["tasting_notes"]), all_scores, removed, pool,
                              reference=r, focus=focus)
    return out


# ----------------------------------------------------------------------------------------
# 5) "How it decided": extra data for the visual explanation in the demo.
#    Not part of the handoff contract; it only describes what the code above already did.
# ----------------------------------------------------------------------------------------

CURRENCY_WORDS = {"ريال", "ريالات", "رس", "sar", "sr", "riyal", "riyals", "rs"}
BUDGET_CUES = {"اقل", "تحت", "حدود", "بحدود", "ميزانيتي", "ميزانيه", "under", "below", "less", "max", "budget",
               "within", "upto"}


def _funnel(pool, filters, u, allow):
    """How many coffees are left after each filter (same checks and order as _apply_filters),
    and at which step each coffee was removed."""
    idx = list(pool)
    steps, removed = [{"key": "all", "count": len(idx)}], {}
    for key, active, keep in _checks(filters, u, allow):
        if not active:
            continue
        after = [i for i in idx if keep(i, COFFEES[i])]
        if key in ("stock", "type") and len(after) == len(idx):
            continue
        kept = set(after)
        for i in idx:
            if i not in kept:
                removed[i] = len(steps)
        idx = after
        steps.append({"key": key, "count": len(idx)})
    return steps, removed


def _query_words(query, u, ref_phrase_ids=None):
    """Each word of the request and what it meant (flavor, brew, budget...). For the highlighted sentence."""
    words = str(query).split()
    flat, owner = [], []
    for wi, w in enumerate(words):
        for t in normalize(w).split():
            flat.append(t)
            owner.append(wi)
    out = [{"text": w, "kind": None, "family": None} for w in words]

    def mark(wi, kind, family=None):
        if out[wi]["kind"] is None:
            out[wi]["kind"] = kind
            out[wi]["family"] = family

    # 1) the coffee name of "like <coffee>"
    if ref_phrase_ids is not None:
        _, phrase = _find_reference(query)
        phrase = set(phrase)
        for j, t in enumerate(flat):
            if (_strip_al(t) if _is_arabic(t) else t) in phrase:
                mark(owner[j], "reference")
        for j, t in enumerate(flat):
            if any(_canonical_tokens(cue) and _canonical_tokens(cue)[0] in token_variants(t)
                   for cue in REFERENCE_CUES if len(_canonical_tokens(cue)) == 1):
                mark(owner[j], "cue")
    # 2) known phrases: flavors, notes, brew, body...
    variants = [token_variants(t) for t in flat]
    excluded = set(u.get("excluded_flavors") or [])
    for i, n, kind, value in MATCHER.find(variants):
        fams = [value] if kind == "family" else (NOTE_FAMILIES.get(value, []) if kind == "note" else [])
        k = kind
        if kind in ("family", "note"):
            k = "exclude" if fams and set(fams) <= excluded and not (set(fams) & set(u.get("flavors") or [])) \
                else "flavor"
        elif kind in ("country", "region"):
            k = "origin"
        elif kind == "saudi_coffee":
            k = "saudi"
        for j in range(i, i + n):
            mark(owner[j], k, fams[0] if fams else None)
    # 3) negation words in front of an excluded flavor
    for j, t in enumerate(flat):
        if t in NEGATION_WORDS and j + 1 < len(flat) and out[owner[j + 1]]["kind"] == "exclude":
            mark(owner[j], "exclude")
    # 4) the budget
    if u.get("max_price_sar") is not None:
        target = float(u["max_price_sar"])
        for j, t in enumerate(flat):
            try:
                is_price = float(t) == target
            except ValueError:
                is_price = False
            if not is_price:
                continue
            mark(owner[j], "budget")
            for k in (j - 1, j - 2):
                if k >= 0 and (token_variants(flat[k]) & BUDGET_CUES or (flat[k] in {"من", "than"} and k == j - 1)):
                    mark(owner[k], "budget")
            if j + 1 < len(flat) and token_variants(flat[j + 1]) & CURRENCY_WORDS:
                mark(owner[j + 1], "budget")
    # 5) "cheap" words and focus words ("its body")
    for j, t in enumerate(flat):
        v = token_variants(t)
        if v & {_strip_al(normalize(w)) for w in CHEAP_WORDS if " " not in w}:
            mark(owner[j], "cheap")
        elif ref_phrase_ids is not None and v & set(FOCUS_WORDS_FLAT):
            mark(owner[j], "focus")
    return out


def _body_guess(i):
    """When the body isn't shown, the KNN still uses the Random Forest probabilities: give the most likely one."""
    if COFFEES[i]["body_level"]:
        return None
    probs = XB["body"][i] / XB["body"][i].sum()
    k = int(np.argmax(probs))
    return [KNN_META["body_names"][k], round(float(probs[k]), 2)]


def _explain(mode, scored, picks, parts_by_i, weights, funnel, words, query_families, query_notes,
             all_scores=None, removed=None, pool=None, reference=None, focus=None):
    """Everything the demo needs to show how the KNN picked the results."""
    pick_ids = [i for i, *_ in picks]
    last = picks[-1][1] if picks else 1.0
    skipped = []
    for i, s, _ in scored:
        if s < last or len(skipped) >= 3:
            break
        if i not in pick_ids:
            skipped.append({"coffee_id": COFFEES[i]["coffee_id"], "name_ar": COFFEES[i]["name_ar"],
                            "roaster_ar": COFFEES[i]["roaster_ar"], "score": round(float(s), 3)})
    total_w = sum(weights.values()) or 1.0
    qnotes = set(query_notes or [])
    top = []
    for rank, (i, s, _) in enumerate(picks, 1):
        c = COFFEES[i]
        parts = parts_by_i.get(i) or {}
        top.append({
            "rank": rank, "coffee_id": c["coffee_id"], "name_ar": c["name_ar"], "roaster_ar": c["roaster_ar"],
            "score": round(float(s), 3), "profile_id": c["profile_id"], "families": c["families"],
            "notes_ar": [NOTE_AR.get(n, n) for n in c["tasting_notes"]],
            "shared_notes_ar": [NOTE_AR.get(n, n) for n in c["tasting_notes"] if n in qnotes],
            "predicted_flavors": c["tasting_notes_are_predicted"],
            "body_level": c["body_level"], "body_is_predicted": c["body_is_predicted"], "body_guess": _body_guess(i),
            "acidity_level": c["acidity_level"], "bitterness_level": c["bitterness_level"],
            "process": c["process"], "origin_country": c["origin_country"],
            "parts": [{"key": b, "match": round(parts[b], 3), "weight": round(weights[b] / total_w, 3),
                       "points": round(weights[b] * parts[b] / total_w, 3)} for b in BLOCK_NAMES if b in parts],
        })
    dots = []
    if all_scores is not None:
        rank_of = {i: k + 1 for k, i in enumerate(pick_ids)}
        removed = removed or {}
        for i in (pool if pool is not None else range(N)):
            dots.append([round(float(all_scores[i]), 3), COFFEES[i]["profile_id"], removed.get(i, 0), rank_of.get(i, 0)])
    ref = None
    if reference is not None:
        rc = COFFEES[reference]
        ref = {"coffee_id": rc["coffee_id"], "name_ar": rc["name_ar"], "roaster_ar": rc["roaster_ar"],
               "families": rc["families"], "notes_ar": [NOTE_AR.get(n, n) for n in rc["tasting_notes"]],
               "profile_id": rc["profile_id"], "body_level": rc["body_level"], "body_guess": _body_guess(reference),
               "acidity_level": rc["acidity_level"], "bitterness_level": rc["bitterness_level"],
               "process": rc["process"], "origin_country": rc["origin_country"]}
    return {
        "mode": mode,
        "focus": focus,
        "words": words,
        "query_families": list(query_families or []),
        "query_notes_ar": [NOTE_AR.get(n, n) for n in (query_notes or [])],
        "reference": ref,
        "funnel": funnel,
        "blocks": [b for b in BLOCK_NAMES if b in weights],
        "weights": {b: round(weights[b] / total_w, 3) for b in BLOCK_NAMES if b in weights},
        "dots": dots,
        "min_score": MIN_SCORE,
        "skipped": skipped,
        "top": top,
    }


def search_coffees(q, limit=10):
    q = (q or "").strip()
    if not q:
        idx = sorted(range(N), key=lambda i: COFFEES[i]["coffee_name"].lower())[:limit]
    else:
        nq = normalize(q)
        direct = []
        for i, c in enumerate(COFFEES):
            text = normalize(" ".join([c["coffee_name"], c["roaster"], c["coffee_name_ar"] or "", c["name_ar"],
                                       c["roaster_ar"]]))
            if nq in text:
                direct.append(i)
        direct.sort(key=lambda i: (not normalize(COFFEES[i]["coffee_name"]).startswith(nq),
                                   len(COFFEES[i]["coffee_name"])))
        idx = direct[:limit]
        if len(idx) < limit:
            fuzzy = [i for i, _ in match_coffee_names(q) if i not in idx]
            idx += fuzzy[:limit - len(idx)]
    return [{"coffee_id": COFFEES[i]["coffee_id"], "coffee_name": COFFEES[i]["coffee_name"],
             "coffee_name_ar": COFFEES[i]["name_ar"], "roaster": COFFEES[i]["roaster"],
             "roaster_ar": COFFEES[i]["roaster_ar"], "origin_country": COFFEES[i]["origin_country"],
             "out_of_stock": COFFEES[i]["out_of_stock"]} for i in idx]


def get_profiles(lang="ar"):
    lang = lang if lang in ("ar", "en") else "ar"
    return [{"profile_id": p["profile_id"], "name": p["name"][lang], "description": p["description"][lang],
             "top_notes": p["top_notes"], "top_notes_ar": [NOTE_AR.get(n, n) for n in p["top_notes"]],
             "n_coffees": p["n_coffees"], "key": p["key"]} for p in PROFILES]


def recommend_by_profile(profile_id, lang="ar", top_k=5, filters=None):
    if profile_id not in PROFILE_BY_ID:
        raise KeyError(profile_id)
    filters = filters or {}
    p = PROFILE_BY_ID[profile_id]
    center = np.array(p["centroid"])
    u = _empty_understanding()
    u.update({"flavors": [f for f, v in zip(FAMILIES, center) if v >= 0.5],
              "max_price_sar": filters.get("max_price_sar"), "brew_method": filters.get("brew_method"),
              "exclude_infused": bool(filters.get("exclude_infused"))})

    def rank(idx):
        """The coffees nearest to the personality's K-Means center (cosine on the 8 families)."""
        out = []
        for i in idx:
            sim = float(FAM[i] @ center / (np.linalg.norm(FAM[i]) * np.linalg.norm(center) + 1e-9))
            reasons = ["in_profile"]
            if filters.get("max_price_sar") is not None:
                reasons.append("within_budget")
            if filters.get("brew_method"):
                reasons.append("suits_brew")
            out.append((i, sim, reasons))
        # ties: coffees described with more real notes first, then the cheaper one
        out.sort(key=lambda s: (-round(s[1], 6), COFFEES[s[0]]["tasting_notes_are_predicted"],
                                -len(COFFEES[s[0]]["tasting_notes"]), LOG_P100[s[0]]))
        return out

    in_profile = [i for i in range(N) if COFFEES[i]["profile_id"] == profile_id]
    indices = _apply_filters(in_profile, filters, {})
    if not indices:
        relaxed, trial = [], dict(filters)
        for key in ["max_price_sar", "brew_method", "exclude_infused"]:
            if trial.get(key):
                trial[key] = None if key != "exclude_infused" else False
                relaxed.append(key)
                indices = _apply_filters(in_profile, trial, {})
                if indices:
                    break
        picks = _pick_diverse(rank(indices), top_k) if indices else []
        return _no_results(u, lang, [_card(i, s, r) for i, s, r in picks], relaxed)
    picks = _pick_diverse(rank(indices), top_k)
    message = (f"هذي أفضل {len(picks)} من شخصية «{p['name']['ar']}»:" if lang == "ar"
               else f"The top {len(picks)} from the “{p['name']['en']}” personality:")
    return _ok(u, message, [_card(i, s, r) for i, s, r in picks])
