"""
Try the recommender from the terminal, without starting the API.

    python try_recommender.py "ابغى محصول مرارته عالية"
    python try_recommender.py "something fruity for V60 under 70 SAR" en
    python try_recommender.py          (runs the demo queries)
"""
import sys

from app import recommender as rec

DEMO_QUERIES = [
    "ابغى محصول مرارته عالية",
    "اقترح لي محصول حموضته خفيفة",
    "أبي شي فواكهي للـ V60 بأقل من 70 ريال",
    "قهوة قوية للاسبريسو",
    "اثيوبي زهري حموضته عالية",
    "اعجبني تيراميسو من بيت التحميص",
    "اعجبني قوام كولومبيا هويلا",
    "something nutty and chocolatey for espresso",
]


def show(query, lang="ar"):
    res = rec.recommend(query, lang=lang)
    print("\n" + "=" * 100)
    print("QUERY:", query)
    print("STATUS:", res["status"], "|", res["message"])
    for option in res["options"]:
        print("   option:", option["label"])
    for c in res["results"]:
        def mark(estimated):
            return "*" if estimated else ""
        print(f"   - {c['coffee_name'][:42]:42} | {c['roaster'][:16]:16} | {c['price_sar']:6.1f} SAR | "
              f"acidity {c['acidity_level']}{mark(c['acidity_is_estimated'])}, "
              f"body {c['body_level']}{mark(c['body_is_predicted'])}, "
              f"bitterness {c['bitterness_level']}{mark(c['bitterness_is_estimated'])} | "
              f"{', '.join(c['tasting_notes'][:3])} | {c['reasons']}")
    print("   (* = estimated, not stated by the roaster)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ar")
    else:
        for q in DEMO_QUERIES:
            show(q)
