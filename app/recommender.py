"""
recommender.py — Coffee Matchmaker recommender.

Same 5 functions, parameters and response format as the handoff doc:
    recommend(query, lang, top_k, filters)
    similar(coffee_id, focus, lang, top_k, filters)
    search_coffees(q, limit)
    get_profiles(lang)
    recommend_by_profile(profile_id, lang, top_k, filters)

How it works:
1. Understand the request: an Arabic + English keyword dictionary finds flavors, taste
   levels (acidity / body / bitterness), origin, process, budget and brew method.
   Coffee names are matched with fuzzy token matching (difflib, no extra package).
2. Rank coffees:
   - free text: a score per coffee from how well it matches each thing the user asked for
   - similar coffee: weighted cosine similarity, with extra weight on what the user liked
3. Return the top coffees with the reasons they were picked.
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FLAVORS = ["fruity", "citrus", "floral", "chocolate", "nutty", "caramel_sweet"]
TASTES = ["acidity", "body", "bitterness"]
LEVELS = {"acidity": ["Low", "Medium", "High"], "body": ["Light", "Medium", "Full"],
          "bitterness": ["Low", "Medium", "High"]}
MAX_PER_ROASTER = 2   # keep results varied


# ----------------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------------
def normalize(text):
    """Lowercase, unify Arabic letter forms, turn Arabic digits into 0-9."""
    text = str(text).lower()
    text = re.sub(r"[ً-ْـ]", "", text)          # diacritics + tatweel
    text = re.sub(r"[أإآ]", "ا", text).replace("ة", "ه").replace("ى", "ي")
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return text


def tokenize(text):
    return re.findall(r"[a-z0-9]+|[؀-ۿ]+", normalize(text))


def strip_al(token):
    """Arabic: drop a leading 'ال' / 'وال' / 'بال' so 'الفواكه' matches 'فواكه'."""
    for prefix in ["وال", "بال", "لل", "ال", "و"]:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix):]
    return token


ARABIC_TO_LATIN = str.maketrans({"ا": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh", "د": "d",
                                 "ذ": "th", "ر": "r", "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t",
                                 "ظ": "z", "ع": "a", "غ": "g", "ف": "f", "ق": "g", "ك": "k", "ل": "l", "م": "m",
                                 "ن": "n", "ه": "h", "و": "u", "ي": "i", "ء": "", "ئ": "i", "ؤ": "u"})


def transliterate(token):
    """Rough Arabic -> Latin spelling, so 'تيراميسو' can match 'tiramisu'."""
    return token.translate(ARABIC_TO_LATIN)


def similar_word(a, b):
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4:
        return SequenceMatcher(None, a, b).ratio() >= 0.85
    return False


# ----------------------------------------------------------------------------
# Keyword dictionary (all keys go through normalize(), so write them naturally)
# ----------------------------------------------------------------------------
FLAVOR_WORDS = {
    "fruity": ["فواكه", "فواكهي", "فاكهي", "فاكهه", "فواكهيه", "توت", "فراوله", "فروت", "استوائي", "مانجو", "خوخ",
               "عنب", "كرز", "تفاح", "اناناس", "fruit", "fruity", "berry", "berries", "strawberry", "tropical",
               "peach", "grape", "cherry", "mango", "apple"],
    "citrus": ["حمضيات", "ليمون", "برتقال", "يوسفي", "جريب", "citrus", "lemon", "lime", "orange", "grapefruit"],
    "floral": ["زهور", "زهري", "زهريه", "ورد", "ياسمين", "لافندر", "floral", "flower", "flowers", "jasmine", "rose"],
    "chocolate": ["شوكولاته", "شوكولا", "شوكلت", "شكولاته", "كاكاو", "chocolate", "chocolatey", "cocoa", "choco"],
    "nutty": ["مكسرات", "بندق", "لوز", "فستق", "جوز", "nut", "nuts", "nutty", "hazelnut", "almond", "peanut"],
    "caramel_sweet": ["كراميل", "عسل", "سكر", "حلو", "حلاوه", "فانيلا", "تمر", "caramel", "honey", "sweet",
                      "sugar", "vanilla", "toffee"],
}
TASTE_WORDS = {
    "acidity": ["حموضه", "حموضته", "حامض", "حمضيه", "حمضي", "حموض", "acidity", "acidic", "acid", "bright"],
    "body": ["قوام", "قوامه", "بودي", "ثقل", "body", "bodied", "mouthfeel"],
    "bitterness": ["مراره", "مرارته", "مرار", "bitter", "bitterness"],
}
LEVEL_WORDS = {
    "Low": ["خفيف", "خفيفه", "قليل", "قليله", "منخفض", "منخفضه", "بسيط", "بسيطه", "ناعم", "ناعمه", "اقل", "low",
            "light", "mild", "less", "soft", "smooth", "little"],
    "High": ["عالي", "عاليه", "قوي", "قويه", "واضح", "واضحه", "مرتفع", "مرتفعه", "كثير", "كثيره", "ثقيل", "ثقيله",
             "ممتلئ", "ممتلئه", "اعلى", "high", "strong", "heavy", "full", "rich", "more", "intense", "bold"],
    "Medium": ["متوسط", "متوسطه", "معتدل", "معتدله", "متوازن", "متوازنه", "medium", "balanced", "moderate"],
}
NEGATION = ["بدون", "بلا", "ما", "مو", "مب", "لا", "غير", "no", "not", "without", "dont", "don't", "avoid"]
REFERENCE_TRIGGERS = ["اعجبني", "عجبني", "حبيت", "جربت", "يشبه", "شبيه", "مشابه", "مثل", "زي", "نفس",
                      "liked", "loved", "similar", "same"]
ARABIC_NAME_WORDS = {   # Arabic words people type for coffee names -> the English word in our names
    "هويلا": "huila", "ويلا": "huila", "قوجي": "guji", "جوجي": "guji", "غوجي": "guji",
    "يرقاتشيف": "yirgacheffe", "يرغاتشيف": "yirgacheffe", "يرجاتشيف": "yirgacheffe", "سيدامو": "sidamo",
    "هامبيلا": "hambela", "همبيلا": "hambela", "شلشلي": "chelchele", "شيلشي": "chelchele", "قيدب": "gedeb",
    "جديب": "gedeb", "انتيوكيا": "antioquia", "توليما": "tolima", "كاوكا": "cauca", "حراز": "haraz",
    "ترازو": "tarrazu", "تارازو": "tarrazu", "نارينو": "narino", "بنكو": "banko", "قوتيتي": "gotiti",
    "مجففه": "natural", "مغسوله": "washed", "لاهوائي": "anaerobic", "بلند": "blend", "مزيج": "blend",
    "ديكاف": "decaf", "اسبريسو": "espresso",
}
COUNTRY_WORDS = {
    "Ethiopia": ["اثيوبيا", "اثيوبي", "اثيوبيه", "ethiopia", "ethiopian"],
    "Colombia": ["كولومبيا", "كولومبي", "كولومبيه", "colombia", "colombian"],
    "Brazil": ["برازيل", "برازيلي", "برازيليه", "brazil", "brazilian"],
    "Kenya": ["كينيا", "كيني", "كينيه", "kenya", "kenyan"],
    "Yemen": ["يمن", "يمني", "يمنيه", "yemen", "yemeni"],
    "Saudi Arabia": ["سعوديه", "سعودي", "saudi"],
    "Uganda": ["اوغندا", "اوغندي", "uganda"],
    "El Salvador": ["سلفادور", "salvador"],
    "Costa Rica": ["كوستاريكا", "costa", "rica"],
    "Indonesia": ["اندونيسيا", "اندونيسي", "indonesia"],
    "Guatemala": ["جواتيمالا", "غواتيمالا", "guatemala"],
    "Rwanda": ["رواندا", "rwanda"],
    "Panama": ["بنما", "panama"],
    "Peru": ["بيرو", "peru"],
    "Honduras": ["هندوراس", "honduras"],
}
PROCESS_WORDS = {
    "Natural": ["مجفف", "مجففه", "طبيعي", "طبيعيه", "natural"],
    "Washed": ["مغسول", "مغسوله", "washed"],
    "Anaerobic": ["لاهوائي", "لاهوائيه", "انيروبك", "anaerobic"],
    "Honey": ["هني", "honey-process"],
}
ESPRESSO_WORDS = ["اسبريسو", "اسبرسو", "اسبريسسو", "لاتيه", "كابتشينو", "كورتادو", "espresso", "latte",
                  "cappuccino", "cortado", "flat"]
FILTER_WORDS = ["فلتر", "v60", "في60", "كيمكس", "دريب", "تقطير", "ايروبرس", "filter", "chemex", "drip",
                "pourover", "aeropress", "pour"]
DECAF_WORDS = ["ديكاف", "منزوع", "decaf", "decaffeinated"]
CHEAP_WORDS = ["رخيص", "رخيصه", "ارخص", "cheap", "cheaper", "affordable", "budget"]
FOCUS_WORDS = {"flavor": ["نكهه", "نكهته", "طعم", "طعمه", "ايحاءات", "flavor", "flavour", "taste", "notes"],
               "price": ["سعر", "سعره", "price", "cost"],
               "origin": ["اصل", "منشا", "بلد", "origin", "country"],
               "process": ["معالجه", "process", "processing"]}


def _norm_list(words):
    return [normalize(w) for w in words]


for _d in [FLAVOR_WORDS, TASTE_WORDS, LEVEL_WORDS, COUNTRY_WORDS, PROCESS_WORDS, FOCUS_WORDS]:
    for _k in _d:
        _d[_k] = _norm_list(_d[_k])
NEGATION, REFERENCE_TRIGGERS = _norm_list(NEGATION), _norm_list(REFERENCE_TRIGGERS)
ARABIC_NAME_WORDS = {normalize(k): v for k, v in ARABIC_NAME_WORDS.items()}
for _country, _words in COUNTRY_WORDS.items():
    for _w in _words:
        ARABIC_NAME_WORDS.setdefault(_w, _country.split()[0].lower())
ESPRESSO_WORDS, FILTER_WORDS = _norm_list(ESPRESSO_WORDS), _norm_list(FILTER_WORDS)
DECAF_WORDS, CHEAP_WORDS = _norm_list(DECAF_WORDS), _norm_list(CHEAP_WORDS)
ALL_COUNTRY_TOKENS = {w for ws in COUNTRY_WORDS.values() for w in ws} | {
    c.split()[0].lower() for c in COUNTRY_WORDS} | {"natural", "washed", "anaerobic", "blend", "decaf", "espresso"}
NOT_NAME_TOKENS = set(REFERENCE_TRIGGERS + NEGATION + ESPRESSO_WORDS + FILTER_WORDS + CHEAP_WORDS +
                      [w for ws in TASTE_WORDS.values() for w in ws] + [w for ws in LEVEL_WORDS.values() for w in ws] +
                      [w for ws in FOCUS_WORDS.values() for w in ws] +
                      _norm_list(["ابي", "ابغى", "ابغي", "اريد", "ودي", "شي", "شيء", "محصول", "قهوه", "في", "من",
                                  "اقل", "ريال", "want", "something", "coffee", "with", "for", "what", "is",
                                  "similar", "to", "a", "an", "i", "me", "it", "its", "this", "that"]))


def find_word(tokens, words):
    """Index of the first token matching any word (exact, without 'ال', or close spelling), else -1."""
    for i, t in enumerate(tokens):
        for w in words:
            if t == w or strip_al(t) == w or (len(w) >= 5 and similar_word(strip_al(t), w)):
                return i
    return -1


def negated(tokens, i):
    return any(t in NEGATION for t in tokens[max(0, i - 2):i])


# ----------------------------------------------------------------------------
# Load data once, when the API starts
# ----------------------------------------------------------------------------
DF = pd.read_csv(DATA / "coffee_enriched.csv", encoding="utf-8-sig").set_index("bean_id", drop=False)
with open(DATA / "profiles.json", encoding="utf-8") as f:
    PROFILES = json.load(f)

for name in FLAVORS:
    DF[name] = DF["note_" + name].astype(float)
for flavor in ["fruity", "floral", "chocolate", "nutty"]:     # predicted flavors: use the probability
    proba = DF["note_" + flavor + "_proba"]
    DF.loc[proba.notna(), flavor] = proba[proba.notna()]
DF["log_price"] = np.log(DF["price_per_100g_sar"])
DF["price_pos"] = (DF["log_price"] - DF["log_price"].min()) / (DF["log_price"].max() - DF["log_price"].min())

IN_STOCK = DF[DF["listed_out_of_stock"] == 0]

# Search text per coffee: English name + roaster + the original Arabic name when there was one
_tr = pd.read_csv(DATA / "translations.csv", encoding="utf-8-sig")
_arabic_names = _tr[_tr["column"] == "coffee_name"].groupby("english")["original"].first()
GENERIC_TOKENS = set(_norm_list(["250g", "250", "1kg", "1", "kg", "g", "200g", "227g", "125g", "500g", "1000g",
                                 "coffee", "beans", "bean", "roastery", "roaster", "roasters", "crop", "specialty",
                                 "قهوه", "محمصه", "محصول", "جرام", "كيلو", "مختصه", "the", "and", "of", "-"]))


def _name_tokens(row):
    text = row["coffee_name"] + " " + str(_arabic_names.get(row["coffee_name"], ""))
    return [t for t in set(tokenize(text)) if t not in GENERIC_TOKENS]


NAME_TOKENS = {bid: _name_tokens(row) for bid, row in DF.iterrows()}

# Words that only name the roaster (e.g. "3bean", or "بيت التحميص" in Roasting House's Arabic names).
# They are taken out of coffee names, and a roaster mentioned in the query only breaks ties.
ROASTER_WORDS = {}
for _roaster, _ids in DF.groupby("roaster").groups.items():
    words = {t for t in tokenize(_roaster) if t not in GENERIC_TOKENS}
    arabic = [[t for t in NAME_TOKENS[b] if re.match(r"[\u0600-\u06ff]", t)] for b in _ids]
    arabic = [a for a in arabic if a]
    counts = pd.Series([t for a in arabic for t in a], dtype=object).value_counts()
    words |= set(counts[(counts >= 2) & (counts >= 0.5 * len(arabic))].index)
    ROASTER_WORDS[_roaster] = words
# also: Arabic words that appear 3+ times in one roaster's names and (almost) never elsewhere
_all_arabic = pd.Series([(DF.at[b, "roaster"], t) for b in NAME_TOKENS for t in NAME_TOKENS[b]
                         if re.match(r"[\u0600-\u06ff]", t)], dtype=object)
_pair_counts = _all_arabic.value_counts()
_token_totals = pd.Series([t for _, t in _all_arabic]).value_counts()
for (_roaster, _token), _n in _pair_counts.items():
    if _n >= 3 and _n >= 0.8 * _token_totals[_token]:
        ROASTER_WORDS[_roaster].add(_token)
_never_roaster = ALL_COUNTRY_TOKENS | set(ARABIC_NAME_WORDS) | {w for ws in PROCESS_WORDS.values() for w in ws} | \
    set(_norm_list(["لاهوائيه", "مجففه", "مغسوله", "القهوه", "البن", "قهوه"]))
for _roaster in ROASTER_WORDS:
    ROASTER_WORDS[_roaster] = {w for w in ROASTER_WORDS[_roaster] if len(w) >= 2 and w not in _never_roaster
                               and strip_al(w) not in _never_roaster}
for _bid in NAME_TOKENS:
    _kept = [t for t in NAME_TOKENS[_bid] if t not in ROASTER_WORDS[DF.at[_bid, "roaster"]]]
    if _kept:
        NAME_TOKENS[_bid] = _kept
ALL_ROASTER_WORDS = {w for ws in ROASTER_WORDS.values() for w in ws}
# Rare words (like "tiramisu") identify a coffee better than common ones (like "colombia" or a roaster's name)
_doc_freq = pd.Series([t for tokens in NAME_TOKENS.values() for t in tokens]).value_counts()
TOKEN_WEIGHT = {t: float(np.log(len(DF) / n)) + 0.1 for t, n in _doc_freq.items()}
FLAVOR_TOKENS = {w for ws in FLAVOR_WORDS.values() for w in ws}
ROASTER_TOKENS = {bid: set(tokenize(r)) for bid, r in DF["roaster"].items()}

# Feature matrix for similarity (all columns between 0 and 1)
_process = pd.get_dummies(DF["process"], prefix="process", dtype=float)
_origin = pd.get_dummies(DF["origin_group"], prefix="origin", dtype=float)
FEATURE_GROUPS = {
    "flavor": FLAVORS,
    "acidity": ["acidity_score"],
    "body": ["body_score"],
    "bitterness": ["bitterness_score"],
    "process": list(_process.columns),
    "origin": list(_origin.columns),
    "price": ["price_pos"],
}
FEATURES = DF[FLAVORS + ["acidity_score", "body_score", "bitterness_score", "price_pos"]].join(_process).join(_origin)
BASE_WEIGHTS = {"flavor": 1.0, "acidity": 1.0, "body": 1.0, "bitterness": 1.0, "process": 0.5, "origin": 0.5,
                "price": 0.3}

# How strongly each coffee shows each flavor: the share of its own tasting notes in that family.
# Used to rank coffees that all "match": "Strawberry, Apricot, Red berries" is more fruity than "Red apple, Cocoa".
NOTE_FAMILY_WORDS = {
    "fruity": ["fruit", "berr", "cherry", "apricot", "peach", "plum", "raisin", "fig", "mango", "pineapple",
               "passion", "kiwi", "melon", "guava", "lychee", "grape", "apple", "pear", "pomegranate", "currant",
               "banana", "papaya", "tropical", "jam", "wine"],
    "citrus": ["citrus", "lemon", "lime", "orange", "grapefruit", "tangerine", "bergamot", "mandarin"],
    "floral": ["floral", "flower", "jasmine", "rose", "lavender", "hibiscus", "blossom", "chamomile"],
    "chocolate": ["chocolate", "cocoa", "cacao"],
    "nutty": ["nut", "almond", "hazelnut", "peanut", "pistachio", "walnut", "cashew", "pecan"],
    "caramel_sweet": ["caramel", "honey", "sugar", "sweet", "vanilla", "toffee", "molasses", "syrup", "maple"],
}
_note_lists = DF["tasting_notes"].where(DF["tasting_notes"] != "Unknown", "").str.lower().str.split("; ")
for _family, _words in NOTE_FAMILY_WORDS.items():
    DF[_family + "_strength"] = [
        (sum(any(w in note for w in _words) for note in notes) / len(notes)) if notes != [""] else 0.0
        for notes in _note_lists]
    DF.loc[DF["has_notes"] == 0, _family + "_strength"] = 0.5 * DF.loc[DF["has_notes"] == 0, _family]
IN_STOCK = DF[DF["listed_out_of_stock"] == 0]

PROFILE_CENTERS = DF.groupby("profile_id")[FLAVORS + ["acidity_score", "body_score", "bitterness_score"]].mean()


# ----------------------------------------------------------------------------
# Building the response
# ----------------------------------------------------------------------------
def _clean(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or value == "Unknown":
        return None
    return value


def _card(row, score, reasons):
    if row["tasting_notes_are_predicted"] == 1:
        notes = [f.replace("_", " & ").title() for f in ["fruity", "floral", "chocolate", "nutty"]
                 if row["note_" + f] == 1]
    else:
        notes = [] if row["tasting_notes"] == "Unknown" else row["tasting_notes"].split("; ")
    return {
        "coffee_id": int(row["bean_id"]),
        "coffee_name": row["coffee_name"],
        "roaster": row["roaster"],
        "roaster_city": _clean(row["roaster_city"]),
        "origin_country": _clean(row["origin_country"]),
        "process": _clean(row["process"]),
        "price_sar": float(row["price_sar"]),
        "weight_g": int(row["weight_g"]),
        "price_per_100g_sar": float(row["price_per_100g_sar"]),
        "price_is_estimated": bool(row["price_was_filled"]),
        "body_level": row["body_level"],
        "body_is_predicted": bool(row["body_is_estimated"]),
        "body_confidence": None,
        "acidity_level": row["acidity_level"],
        "acidity_is_estimated": bool(row["acidity_is_estimated"]),
        "bitterness_level": row["bitterness_level"],
        "bitterness_is_estimated": bool(row["bitterness_is_estimated"]),
        "tasting_notes": notes,
        "tasting_notes_are_predicted": bool(row["tasting_notes_are_predicted"]),
        "suits_espresso": bool(row["suits_espresso"]),
        "suits_filter": bool(row["suits_filter"]),
        "profile_id": int(row["profile_id"]),
        "match_score": round(float(score), 2),
        "reasons": reasons,
        "product_url": row["product_url"],
    }


def _understood(ref=None, focus="overall", flavors=None, avoid=None, tastes=None, filters=None,
                origin=None, process=None):
    filters = filters or {}
    return {
        "reference_coffee_id": None if ref is None else int(ref["bean_id"]),
        "reference_coffee_name": None if ref is None else ref["coffee_name"],
        "focus": focus,
        "flavors": flavors or [],
        "avoid_flavors": avoid or [],
        "taste_levels": tastes or {},
        "origin_country": origin,
        "process": process,
        "max_price_sar": filters.get("max_price_sar"),
        "brew_method": filters.get("brew_method"),
    }


def _response(status, understood, message, results=None, options=None):
    return {"status": status, "understood": understood, "message": message,
            "results": results or [], "options": options or []}


def _pick_top(ranked, top_k):
    """Take the best coffees, at most MAX_PER_ROASTER per roaster."""
    picked, per_roaster = [], {}
    for bid in ranked:
        roaster = DF.at[bid, "roaster"]
        if per_roaster.get(roaster, 0) >= MAX_PER_ROASTER:
            continue
        picked.append(bid)
        per_roaster[roaster] = per_roaster.get(roaster, 0) + 1
        if len(picked) == top_k:
            break
    return picked


# ----------------------------------------------------------------------------
# Filters
# ----------------------------------------------------------------------------
def _apply_filters(df, filters):
    """Hard filters: budget and infused. Returns (filtered df, relaxed: bool)."""
    filters = filters or {}
    out = df
    if filters.get("exclude_infused"):
        out = out[out["is_infused"] == 0]
    if filters.get("max_price_sar") is not None:
        out = out[out["price_sar"] <= filters["max_price_sar"]]
    return out


def _brew_bonus(df, brew):
    """Brew method is a soft preference: many roasters don't mention it, so a 0 means 'unknown'."""
    if brew == "espresso":
        return df["suits_espresso"].astype(float)
    if brew == "filter":
        return df["suits_filter"].astype(float)
    return pd.Series(0.0, index=df.index)


def _common_reasons(row, filters):
    reasons = []
    filters = filters or {}
    if filters.get("max_price_sar") is not None and row["price_sar"] <= filters["max_price_sar"]:
        reasons.append("within_budget")
    brew = filters.get("brew_method")
    if (brew == "espresso" and row["suits_espresso"] == 1) or (brew == "filter" and row["suits_filter"] == 1):
        reasons.append("suits_brew")
    return reasons


# ----------------------------------------------------------------------------
# Understanding free text
# ----------------------------------------------------------------------------
def _parse(query):
    tokens = tokenize(query)
    text = normalize(query)
    parsed = {"flavors": [], "avoid": [], "tastes": {}, "origin": None, "process": None, "brew": None,
              "max_price": None, "decaf": False, "cheap": False, "focus": None, "reference_wanted": False}

    for flavor, words in FLAVOR_WORDS.items():
        i = find_word(tokens, words)
        if i >= 0:
            (parsed["avoid"] if negated(tokens, i) else parsed["flavors"]).append(flavor)

    for taste, words in TASTE_WORDS.items():
        i = find_word(tokens, words)
        if i < 0:
            continue
        if negated(tokens, i):
            parsed["tastes"][taste] = "Low"
            continue
        window = tokens[max(0, i - 3):i + 4]
        level = None
        for name in ["Low", "High", "Medium"]:
            if find_word(window, LEVEL_WORDS[name]) >= 0:
                level = name
                break
        parsed["tastes"][taste] = level   # None = the taste was mentioned without a level
    if not parsed["tastes"]:
        # "قهوة قوية / ثقيلة" = strong coffee, "قهوة خفيفة" = mild coffee, "bright" = high acidity
        if find_word(tokens, _norm_list(["قويه", "قوي", "ثقيله", "ثقيل", "strong", "heavy", "bold"])) >= 0:
            parsed["tastes"] = {"body": "High", "bitterness": "High"}
        elif find_word(tokens, _norm_list(["خفيفه", "خفيف", "mild", "light"])) >= 0:
            parsed["tastes"] = {"body": "Low", "bitterness": "Low"}
        elif "bright" in tokens:
            parsed["tastes"] = {"acidity": "High"}

    for country, words in COUNTRY_WORDS.items():
        if find_word(tokens, words) >= 0:
            parsed["origin"] = country
            break
    for process, words in PROCESS_WORDS.items():
        if find_word(tokens, words) >= 0:
            parsed["process"] = process
            break

    if find_word(tokens, ESPRESSO_WORDS) >= 0:
        parsed["brew"] = "espresso"
    elif find_word(tokens, FILTER_WORDS) >= 0 or "v60" in text.replace(" ", ""):
        parsed["brew"] = "filter"

    money = re.search(r"(\d+(?:\.\d+)?)\s*(?:ريال|ر\.?س|sar|sr|rs)", text)
    if not money:
        money = re.search(r"(?:اقل من|اقل|تحت|حدود|ب|under|below|less than|max|budget)\s*(\d+(?:\.\d+)?)", text)
    if money:
        parsed["max_price"] = float(money.group(1))

    parsed["decaf"] = find_word(tokens, DECAF_WORDS) >= 0
    parsed["cheap"] = find_word(tokens, CHEAP_WORDS) >= 0
    parsed["reference_wanted"] = any(t in REFERENCE_TRIGGERS for t in tokens)
    for focus, words in FOCUS_WORDS.items():
        if find_word(tokens, words) >= 0:
            parsed["focus"] = focus
            break
    return parsed, tokens


def _match_coffee_names(tokens, wanted=True):
    """
    Score every coffee name against the query, both ways:
    - how much of the NAME appears in the query, and
    - how much of the QUERY's name-like words appear in the name,
    with rare words (like "tiramisu") counting more than common ones (like "colombia").
    """
    query, roasters_mentioned = [], set()
    for t in tokens:
        if t in GENERIC_TOKENS or t in NOT_NAME_TOKENS:
            continue
        latin = transliterate(t) if re.match(r"[\u0600-\u06ff]", t) else None
        found = {r for r, ws in ROASTER_WORDS.items()
                 if t in ws or strip_al(t) in ws
                 or (latin and len(latin) >= 5 and any(SequenceMatcher(None, latin, w).ratio() >= 0.75 for w in ws))}
        if found:
            roasters_mentioned |= found
            continue
        t = strip_al(t) if t not in ARABIC_NAME_WORDS else t
        if t in GENERIC_TOKENS or t in NOT_NAME_TOKENS:
            continue
        query.append(ARABIC_NAME_WORDS.get(t, t))
    if not query:
        return pd.Series(dtype=float), roasters_mentioned

    def word_hits(q, name_token):
        if similar_word(strip_al(name_token), q):
            return True
        if re.match(r"[\u0600-\u06ff]", q) and len(q) >= 5:
            return SequenceMatcher(None, name_token, transliterate(q)).ratio() >= 0.75
        return False

    per_coffee, query_used = {}, set()
    for bid, name_tokens in NAME_TOKENS.items():
        pairs = [(q, nt) for q in query for nt in name_tokens if word_hits(q, nt)]
        if not pairs:
            continue
        name_hits = {nt for _, nt in pairs}
        query_hits_here = {q for q, _ in pairs}
        # country, process and flavor words alone don't identify a coffee ("I liked fruity" is a flavor request)
        if not [q for q in query_hits_here
                if q not in ALL_COUNTRY_TOKENS and q not in FLAVOR_TOKENS and find_word([q], list(FLAVOR_TOKENS)) < 0]:
            continue
        query_hits = {q for q, _ in pairs}
        query_used |= query_hits
        per_coffee[bid] = (name_hits, query_hits)

    def weight(t):
        return TOKEN_WEIGHT.get(t, 3.0)

    # a query word weighs as much as the rarest name word it matched
    q_weight = {}
    for bid, (name_hits, query_hits) in per_coffee.items():
        for q in query_hits:
            matched = [weight(nt) for nt in name_hits if word_hits(q, nt)]
            if matched:
                q_weight[q] = max(q_weight.get(q, 0), max(matched))
    query_total = sum(q_weight.get(q, 3.0) for q in query_used) or 1.0
    scores = {}
    for bid, (name_hits, query_hits) in per_coffee.items():
        name_cover = 0.0
        for is_arabic in (False, True):   # a name can have an English and an Arabic version
            part = [nt for nt in NAME_TOKENS[bid] if bool(re.match(r"[\u0600-\u06ff]", nt)) == is_arabic]
            if part:
                name_cover = max(name_cover, sum(weight(h) for h in name_hits if h in part) /
                                 sum(weight(t) for t in part))
        query_cover = sum(q_weight.get(q, 3.0) for q in query_hits) / query_total
        # F2 score: finding all the words the user typed matters more than covering the whole name
        scores[bid] = 5 * name_cover * query_cover / (4 * name_cover + query_cover)
    scores = pd.Series(scores, dtype=float).sort_values(ascending=False)
    return scores, roasters_mentioned


def _find_reference(tokens, wanted):
    matches, roasters = _match_coffee_names(tokens, wanted)
    if matches.empty:
        return None, []
    best = matches.iloc[0]
    if best < (0.34 if wanted else 0.75):
        return None, []
    close = matches[matches >= best * 0.8]
    if roasters:   # "Ethiopia Guji from 3Bean": the roaster settles it
        from_roaster = close[[DF.at[b, "roaster"] in roasters for b in close.index]]
        if len(from_roaster):
            close = from_roaster
    if len(close) == 1:
        return int(close.index[0]), []
    return None, [int(b) for b in close.index[:5]]


# ----------------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------------
LEVEL_AR = {"Low": "خفيفة", "Medium": "متوسطة", "High": "عالية", "Light": "خفيف", "Full": "ثقيل"}
TASTE_AR = {"acidity": "حموضة", "body": "قوام", "bitterness": "مرارة"}
FLAVOR_AR = {"fruity": "فواكه", "citrus": "حمضيات", "floral": "زهور", "chocolate": "شوكولاتة", "nutty": "مكسرات",
             "caramel_sweet": "حلاوة وكراميل"}
FOCUS_AR = {"body": "القوام", "acidity": "الحموضة", "bitterness": "المرارة", "flavor": "النكهة", "price": "السعر",
            "origin": "بلد المنشأ", "process": "طريقة المعالجة", "overall": "كل شي"}


def _describe(parsed, lang):
    parts = []
    if lang == "ar":
        if parsed["flavors"]:
            parts.append("نكهات " + " و".join(FLAVOR_AR[f] for f in parsed["flavors"]))
        for taste, level in parsed["tastes"].items():
            if level:
                word = LEVEL_AR["Light" if taste == "body" and level == "Low" else
                                "Full" if taste == "body" and level == "High" else level]
                parts.append(f"{TASTE_AR[taste]} {word}")
        if parsed["avoid"]:
            parts.append("بدون " + " و".join(FLAVOR_AR[f] for f in parsed["avoid"]))
        if parsed["origin"]:
            parts.append(f"من {parsed['origin']}")
        if parsed["process"]:
            parts.append(f"معالجة {parsed['process']}")
        if parsed["decaf"]:
            parts.append("منزوعة الكافيين")
        if parsed["cheap"]:
            parts.append("سعر أقل")
        if parsed["brew"]:
            parts.append("للإسبريسو" if parsed["brew"] == "espresso" else "للفلتر")
        if parsed["max_price"]:
            parts.append(f"بأقل من {parsed['max_price']:g} ريال")
        return "، ".join(parts)
    if parsed["flavors"]:
        parts.append(" & ".join(parsed["flavors"]).replace("_", " "))
    for taste, level in parsed["tastes"].items():
        if level:
            parts.append(f"{level.lower()} {taste}")
    if parsed["avoid"]:
        parts.append("no " + ", ".join(parsed["avoid"]).replace("_", " "))
    if parsed["origin"]:
        parts.append(f"from {parsed['origin']}")
    if parsed["process"]:
        parts.append(f"{parsed['process'].lower()} process")
    if parsed["decaf"]:
        parts.append("decaf")
    if parsed["cheap"]:
        parts.append("lower price")
    if parsed["brew"]:
        parts.append(f"for {parsed['brew']}")
    if parsed["max_price"]:
        parts.append(f"under {parsed['max_price']:g} SAR")
    return ", ".join(parts)


# ----------------------------------------------------------------------------
# 1) Free text
# ----------------------------------------------------------------------------
def recommend(query, lang="ar", top_k=5, filters=None):
    parsed, tokens = _parse(query)
    filters = dict(filters or {})
    if filters.get("max_price_sar") is None and parsed["max_price"] is not None:
        filters["max_price_sar"] = parsed["max_price"]
    if filters.get("brew_method") is None and parsed["brew"] is not None:
        filters["brew_method"] = parsed["brew"]

    # "I liked X" -> similar()
    ref_id, options = _find_reference(tokens, parsed["reference_wanted"])
    if options and parsed["reference_wanted"]:
        focus = _focus_from(parsed)
        msg = "لقيت أكثر من محصول بهذا الاسم، أي واحد تقصد؟" if lang == "ar" else \
            "I found more than one coffee with that name. Which one do you mean?"
        opts = [{"coffee_id": b, "label": f"{DF.at[b, 'coffee_name']} — {DF.at[b, 'roaster']}"} for b in options]
        return _response("clarify", _understood(focus=focus, filters=filters), msg, options=opts)
    if ref_id is not None:
        return similar(ref_id, _focus_from(parsed), lang, top_k, filters)

    wants_something = parsed["flavors"] or parsed["avoid"] or any(parsed["tastes"].values()) or parsed["origin"] \
        or parsed["process"] or parsed["decaf"] or parsed["cheap"] or filters.get("brew_method") \
        or filters.get("max_price_sar") is not None
    understood = _understood(flavors=parsed["flavors"], avoid=parsed["avoid"],
                             tastes={k: v for k, v in parsed["tastes"].items() if v}, filters=filters,
                             origin=parsed["origin"], process=parsed["process"])
    if not wants_something:
        msg = ("ما فهمت طلبك. جرّب مثلًا: \"أبي قهوة فواكهية للـ V60 بأقل من 70 ريال\" أو \"حموضة خفيفة\""
               if lang == "ar" else
               'I couldn\'t understand that. Try: "something fruity for V60 under 70 SAR" or "low acidity"')
        return _response("no_results", understood, msg)

    # Decaf and Saudi-style coffee only when the user asks for them
    pool = IN_STOCK
    pool = pool[pool["product_type"] == "decaf"] if parsed["decaf"] else pool[pool["product_type"] != "decaf"]
    if parsed["origin"] == "Saudi Arabia":
        pool = pool[(pool["origin_country"] == "Saudi Arabia") | (pool["product_type"] == "saudi_coffee")]
    else:
        pool = pool[(pool["product_type"] != "saudi_coffee") & (pool["is_spiced"] == 0)]
        if parsed["origin"] is not None and (pool["origin_country"] == parsed["origin"]).any():
            pool = pool[pool["origin_country"] == parsed["origin"]]
    if parsed["process"] is not None and (pool["process"] == parsed["process"]).any():
        pool = pool[pool["process"] == parsed["process"]]

    candidates = _apply_filters(pool, filters)
    relaxed = False
    if candidates.empty:
        candidates, relaxed = pool, True

    score = pd.Series(0.0, index=candidates.index)
    max_score = 0.0
    for flavor in parsed["flavors"]:
        score += 2.0 * candidates[flavor] + 0.5 * candidates[flavor + "_strength"]
        max_score += 2.5
    for flavor in parsed["avoid"]:
        score -= 2.0 * candidates[flavor]
    for taste, level in parsed["tastes"].items():
        if not level:
            continue
        s = candidates[taste + "_score"]
        closeness = {"Low": 1 - s, "High": s, "Medium": 1 - (s - 0.5).abs() * 2}[level]
        wanted_level = LEVELS[taste][["Low", "Medium", "High"].index(level)]
        stated = candidates[taste + "_is_estimated"] == 0
        stated_match = stated & (candidates[taste + "_level"] == wanted_level)
        stated_miss = stated & (candidates[taste + "_level"] != wanted_level)
        # a value the roaster stated beats our estimate: reward a match, push a mismatch down
        score += 2.0 * closeness + 0.5 * stated_match - 2.0 * stated_miss
        max_score += 2.5
    brew_bonus = _brew_bonus(candidates, filters.get("brew_method"))
    score += 0.5 * brew_bonus
    max_score += 0.5 if filters.get("brew_method") else 0
    if parsed["cheap"]:
        price_rank = candidates["price_sar"].rank(pct=True)    # the bag price the user sees
        score += 1.0 * (1 - price_rank)
        max_score += 1.0
    score += 0.2 * candidates["has_notes"]           # small preference for coffees with real notes
    max_score += 0.2
    match = (score / max_score).clip(0, 1)
    # Ties (common for short requests) are broken by a tiny, fixed-per-request shuffle instead of file order,
    # so results aren't always the roasters that come first alphabetically. Same request -> same results.
    rng = np.random.default_rng(sum(ord(c) for c in normalize(query)))
    match = match + rng.uniform(0, 0.001, len(match))

    order = match.sort_values(ascending=False, kind="stable").index
    top = _pick_top(order, top_k)

    results = []
    for bid in top:
        row = DF.loc[bid]
        reasons = []
        if parsed["flavors"] and any(row["note_" + f] == 1 for f in parsed["flavors"]):
            reasons.append("matches_flavor")
        for taste, level in parsed["tastes"].items():
            if level and row[taste + "_level"] == LEVELS[taste][["Low", "Medium", "High"].index(level)]:
                reasons.append("matches_" + taste)
        if parsed["origin"] and row["origin_country"] == parsed["origin"]:
            reasons.append("same_origin")
        if parsed["process"] and row["process"] == parsed["process"]:
            reasons.append("same_process")
        reasons += _common_reasons(row, filters)
        results.append(_card(row, match[bid], reasons))

    wanted = _describe(parsed, lang)
    if relaxed:
        msg = (f"ما لقينا شي بهذي الميزانية. هذي أقرب الخيارات لطلبك ({wanted}) بسعر أعلى:" if lang == "ar" else
               f"Nothing fits that budget. Here are the closest matches for {wanted}, at a higher price:")
        return _response("no_results", understood, msg, results)
    msg = (f"فهمت إنك تبي: {wanted}. هذي أقرب {len(results)}:" if lang == "ar" else
           f"Looking for: {wanted}. Here are the top {len(results)}:")
    return _response("ok", understood, msg, results)


def _focus_from(parsed):
    mentioned = [t for t in parsed["tastes"]]
    if mentioned:
        return mentioned[0]
    if parsed["focus"]:
        return parsed["focus"]
    if parsed["flavors"]:
        return "flavor"
    return "overall"


# ----------------------------------------------------------------------------
# 2) Similar to a coffee
# ----------------------------------------------------------------------------
def similar(coffee_id, focus="overall", lang="ar", top_k=5, filters=None):
    if coffee_id not in DF.index:
        raise KeyError(coffee_id)
    ref = DF.loc[coffee_id]
    filters = filters or {}

    pool = IN_STOCK.drop(index=coffee_id, errors="ignore")
    if ref["product_type"] != "saudi_coffee":
        pool = pool[(pool["product_type"] != "saudi_coffee") & (pool["is_spiced"] == 0)]
    if ref["product_type"] != "decaf":
        pool = pool[pool["product_type"] != "decaf"]
    candidates = _apply_filters(pool, filters)
    relaxed = candidates.empty
    if relaxed:
        candidates = pool

    # Focus on what the user liked
    if focus in TASTES:
        same = candidates[candidates[focus + "_level"] == ref[focus + "_level"]]
        if len(same) >= top_k:
            candidates = same
    elif focus == "price":
        near = candidates[(candidates["price_per_100g_sar"] / ref["price_per_100g_sar"]).between(0.8, 1.2)]
        if len(near) >= top_k:
            candidates = near
    elif focus in ("origin", "process"):
        column = "origin_country" if focus == "origin" else "process"
        same = candidates[candidates[column] == ref[column]]
        if len(same) >= top_k:
            candidates = same

    weights = dict(BASE_WEIGHTS)
    if focus in ("flavor", "acidity", "body", "bitterness"):
        weights[focus] = 4.0
    w = np.concatenate([np.full(len(FEATURE_GROUPS[g]), np.sqrt(weights[g])) for g in FEATURE_GROUPS])
    columns = [c for g in FEATURE_GROUPS for c in FEATURE_GROUPS[g]]
    A = FEATURES.loc[candidates.index, columns].values * w
    b = FEATURES.loc[coffee_id, columns].values.astype(float) * w
    sims = A @ b / (np.linalg.norm(A, axis=1) * np.linalg.norm(b) + 1e-9)
    sims = pd.Series(sims, index=candidates.index)
    sims += 0.1 * _brew_bonus(candidates, filters.get("brew_method"))

    top = _pick_top(sims.sort_values(ascending=False, kind="stable").index, top_k)
    results = []
    ref_flavors = {f for f in FLAVORS if ref["note_" + f] == 1}
    for bid in top:
        row = DF.loc[bid]
        reasons = []
        for taste in TASTES:
            if row[taste + "_level"] == ref[taste + "_level"] and (focus == taste or taste == "body"):
                reasons.append("same_" + taste)
        row_flavors = {f for f in FLAVORS if row["note_" + f] == 1}
        if ref_flavors and len(ref_flavors & row_flavors) / len(ref_flavors | row_flavors) >= 0.5:
            reasons.append("similar_flavor")
        if row["origin_country"] == ref["origin_country"] and ref["origin_country"] not in ("Multiple", "Unknown"):
            reasons.append("same_origin")
        if row["process"] == ref["process"] and ref["process"] != "Unknown":
            reasons.append("same_process")
        ratio = row["price_per_100g_sar"] / ref["price_per_100g_sar"]
        if ratio <= 0.9:
            reasons.append("cheaper")
        elif ratio <= 1.15:
            reasons.append("similar_price")
        reasons += _common_reasons(row, filters)
        results.append(_card(row, min(max(sims[bid], 0), 1), reasons))

    understood = _understood(ref=ref, focus=focus, filters=filters)
    estimated_note = ""
    if focus in TASTES and ref[focus + "_is_estimated"] == 1:
        estimated_note = (f" ({FOCUS_AR[focus]} في هذا المحصول تقديري لأن المحمصة ما ذكرته)" if lang == "ar" else
                          f" (this coffee's {focus} isn't listed by the roaster, so it's estimated)")
    if relaxed:
        msg = (f"ما لقينا شي بهذي الميزانية يشبه {ref['coffee_name']}. هذي أقرب الخيارات بسعر أعلى:" if lang == "ar"
               else f"Nothing in that budget is similar to {ref['coffee_name']}. Closest options at a higher price:")
        return _response("no_results", understood, msg, results)
    if lang == "ar":
        msg = f"محاصيل تشبه {ref['coffee_name']} في {FOCUS_AR.get(focus, 'كل شي')}{estimated_note}. هذي أقرب {len(results)}:"
    else:
        msg = f"Coffees similar to {ref['coffee_name']} ({focus}){estimated_note}. Top {len(results)}:"
    return _response("ok", understood, msg, results)


# ----------------------------------------------------------------------------
# 3) Search (autocomplete)
# ----------------------------------------------------------------------------
def search_coffees(q, limit=10):
    q_tokens = tokenize(q)
    if not q_tokens:
        return []
    q_text = normalize(q)
    scores = {}
    for bid, row in DF.iterrows():
        haystack = normalize(row["coffee_name"] + " " + row["roaster"] + " " +
                             str(_arabic_names.get(row["coffee_name"], "")))
        if q_text in haystack:
            scores[bid] = 2.0
            continue
        words = tokenize(haystack)
        hits = sum(any(w.startswith(t) or similar_word(w, t) for w in words) for t in q_tokens)
        if hits:
            scores[bid] = hits / len(q_tokens)
    ranked = sorted(scores, key=lambda b: (-scores[b], DF.at[b, "coffee_name"]))[:limit]
    return [{"coffee_id": int(b), "coffee_name": DF.at[b, "coffee_name"], "roaster": DF.at[b, "roaster"]}
            for b in ranked]


# ----------------------------------------------------------------------------
# 4) Profiles
# ----------------------------------------------------------------------------
def get_profiles(lang="ar"):
    return [{"profile_id": p["profile_id"], "name": p["name"][lang], "description": p["description"][lang],
             "top_notes": p["top_notes"], "n_coffees": p["n_coffees"]} for p in PROFILES]


def recommend_by_profile(profile_id, lang="ar", top_k=5, filters=None):
    if profile_id not in PROFILE_CENTERS.index:
        raise KeyError(profile_id)
    filters = filters or {}
    profile = next(p for p in PROFILES if p["profile_id"] == profile_id)
    pool = IN_STOCK[(IN_STOCK["profile_id"] == profile_id) & (IN_STOCK["is_spiced"] == 0) &
                    (~IN_STOCK["product_type"].isin(["saudi_coffee", "decaf"]))]
    candidates = _apply_filters(pool, filters)
    relaxed = candidates.empty
    if relaxed:
        candidates = pool

    center = PROFILE_CENTERS.loc[profile_id].values
    columns = FLAVORS + ["acidity_score", "body_score", "bitterness_score"]
    distance = np.linalg.norm(candidates[columns].values - center, axis=1)
    closeness = pd.Series(1 - distance / np.sqrt(len(columns)), index=candidates.index)
    closeness += 0.05 * candidates["has_notes"] + 0.1 * _brew_bonus(candidates, filters.get("brew_method"))

    top = _pick_top(closeness.sort_values(ascending=False, kind="stable").index, top_k)
    results = [_card(DF.loc[b], min(max(closeness[b], 0), 1), ["in_profile"] + _common_reasons(DF.loc[b], filters))
               for b in top]
    understood = _understood(filters=filters)
    name = profile["name"][lang]
    if relaxed:
        msg = (f"ما لقينا شي من \"{name}\" بهذي الميزانية. هذي أقرب الخيارات بسعر أعلى:" if lang == "ar" else
               f"Nothing from \"{name}\" fits that budget. Closest options at a higher price:")
        return _response("no_results", understood, msg, results)
    msg = (f"أفضل محاصيل \"{name}\":" if lang == "ar" else f"Top coffees from \"{name}\":")
    return _response("ok", understood, msg, results)
