# recommender.py (MOCK) — نسخة وهمية بنفس الدوال اللي بتسلمها رغد.
# ترجع محاصيل حقيقية من البيانات، لكن الاختيار عشوائي. لما يوصل ملف رغد، استبدل هذا الملف فقط.
import random
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "saudi_specialty_coffee_beans_clean.csv"
DF = pd.read_csv(DATA)
IN_STOCK = DF[DF["listed_out_of_stock"] == 0]

PROFILES = [
    {"profile_id": 0, "name": {"ar": "فواكهي وزاهي", "en": "Fruity & bright"}, "top_notes": ["Strawberry", "Citrus"]},
    {"profile_id": 1, "name": {"ar": "شوكولاتة ومكسرات", "en": "Chocolate & nutty"}, "top_notes": ["Chocolate", "Hazelnut"]},
    {"profile_id": 2, "name": {"ar": "زهري وخفيف", "en": "Floral & light"}, "top_notes": ["Jasmine", "Bergamot"]},
    {"profile_id": 3, "name": {"ar": "حلو ومتوازن", "en": "Sweet & balanced"}, "top_notes": ["Caramel", "Honey"]},
]


def _unknown_to_none(value):
    return None if value == "Unknown" else value


def _card(row, score, reasons):
    notes = row["tasting_notes"]
    return {
        "coffee_id": int(row["bean_id"]),
        "coffee_name": row["coffee_name"],
        "roaster": row["roaster"],
        "roaster_city": _unknown_to_none(row["roaster_city"]),
        "origin_country": _unknown_to_none(row["origin_country"]),
        "process": _unknown_to_none(row["process"]),
        "price_sar": float(row["price_sar"]),
        "weight_g": int(row["weight_g"]),
        "price_per_100g_sar": float(row["price_per_100g_sar"]),
        "price_is_estimated": bool(row["price_was_filled"]),
        "body_level": _unknown_to_none(row["body_level"]),
        "body_is_predicted": False,
        "body_confidence": None,
        "acidity_level": random.choice(["Low", "Medium", "High"]),
        "acidity_is_estimated": True,
        "tasting_notes": [] if notes == "Unknown" else notes.split("; "),
        "tasting_notes_are_predicted": False,
        "suits_espresso": bool(row["suits_espresso"]),
        "suits_filter": bool(row["suits_filter"]),
        "match_score": score,
        "reasons": reasons,
        "product_url": row["product_url"],
    }


def _apply_filters(df, filters):
    filters = filters or {}
    if filters.get("max_price_sar") is not None:
        df = df[df["price_sar"] <= filters["max_price_sar"]]
    if filters.get("brew_method") == "espresso":
        df = df[df["suits_espresso"] == 1]
    elif filters.get("brew_method") == "filter":
        df = df[df["suits_filter"] == 1]
    if filters.get("exclude_infused"):
        df = df[df["is_infused"] == 0]
    return df


def _response(df, top_k, understood, message, reasons):
    if len(df) == 0:
        return {"status": "no_results", "understood": understood,
                "message": "ما لقينا شي يطابق الفلاتر، جرّب ميزانية أعلى.",
                "results": [], "options": []}
    sample = df.sample(min(top_k, len(df)))
    results = [_card(r, round(0.92 - i * 0.04, 2), reasons) for i, (_, r) in enumerate(sample.iterrows())]
    return {"status": "ok", "understood": understood, "message": message, "results": results, "options": []}


def _understood(filters=None, focus="overall", ref=None):
    filters = filters or {}
    return {
        "reference_coffee_id": None if ref is None else int(ref["bean_id"]),
        "reference_coffee_name": None if ref is None else ref["coffee_name"],
        "focus": focus,
        "flavors": [],
        "max_price_sar": filters.get("max_price_sar"),
        "brew_method": filters.get("brew_method"),
    }


def recommend(query, lang="ar", top_k=5, filters=None):
    df = _apply_filters(IN_STOCK, filters)
    return _response(df, top_k, _understood(filters), f"(MOCK) نتائج لطلبك: {query}", ["similar_flavor"])


def similar(coffee_id, focus="overall", lang="ar", top_k=5, filters=None):
    match = DF[DF["bean_id"] == coffee_id]
    if len(match) == 0:
        raise KeyError(coffee_id)
    ref = match.iloc[0]
    df = _apply_filters(IN_STOCK[IN_STOCK["bean_id"] != coffee_id], filters)
    reasons = ["same_body"] if focus == "body" else ["similar_flavor"]
    return _response(df, top_k, _understood(filters, focus, ref),
                     f"(MOCK) محاصيل قريبة من {ref['coffee_name']}:", reasons)


def search_coffees(q, limit=10):
    hits = DF[DF["coffee_name"].str.contains(q, case=False, regex=False)].head(limit)
    return [{"coffee_id": int(r["bean_id"]), "coffee_name": r["coffee_name"], "roaster": r["roaster"]}
            for _, r in hits.iterrows()]


def get_profiles(lang="ar"):
    return [{"profile_id": p["profile_id"], "name": p["name"][lang], "description": "",
             "top_notes": p["top_notes"], "n_coffees": 0} for p in PROFILES]


def recommend_by_profile(profile_id, lang="ar", top_k=5, filters=None):
    if profile_id not in [p["profile_id"] for p in PROFILES]:
        raise KeyError(profile_id)
    df = _apply_filters(IN_STOCK, filters)
    return _response(df, top_k, _understood(filters), "(MOCK) محاصيل من شخصيتك:", ["in_profile"])
