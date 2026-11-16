# Arabic display names for the app (the app shows everything in Arabic).
# The data itself stays in English (section 13); these are only for display.
import re

ROASTER_AR = {
    "12 Cups Coffee": "12 Cups Coffee", "3Bean Roastery": "ثري بين", "8th Day Roastery": "اليوم الثامن",
    "Abla Roastery": "عبلة", "Al Sarawe Roastery": "Al Sarawe Roastery", "Alton Roastery": "Alton Roastery",
    "Alwal Albari Roastery": "الوعل البري", "Andes Roastery": "Andes Roastery", "Aqahi Roastery": "Aqahi Roastery",
    "Arriyadh Roaster": "محمصة الرياض", "Ash Roastery": "Ash Roastery", "Basaten Albun Roastery": "بساتين البن",
    "Black Knight": "الفارس الأسود", "Black Sip Roastery": "بلاك سيب", "Black Stamp Roastery": "بلاك ستامب",
    "Breehant Roastery": "بريهانت", "Brew92": "Brew92", "Bunista": "Bunista", "C&B Roastery": "C&B Roastery",
    "Caffeine Lab": "Caffeine Lab", "Camel Step": "Camel Step", "Carmalah Roastery": "Carmalah Roastery",
    "Curve Roastery": "كيرف", "Dapilio Roastery": "Dapilio Roastery", "Drip On": "Drip On", "Elixir Bunn": "Elixir Bunn",
    "Five One Roastery": "فايف ون", "Flint Roastery": "فلنت", "Gotah Roastery": "قوته",
    "Gusn Coffee Roastery": "غصن القهوة", "Half World Roastery": "هاف ورلد",
    "Hasad Albunn Coffee Roaster": "Hasad Albunn Coffee Roaster", "Hasil Roastery": "حصيل", "Hayzam Roastery": "هيزم",
    "Hjeen": "هجين", "Jorn Roastery": "جرن", "Kanaf Roasters": "Kanaf Roasters", "Karaz Albun Roastery": "كرز البن",
    "Kawn Roastery": "كون", "Kiffa Coffee": "كفة", "Kuf Roastery": "كوف", "Marid Roastery": "Marid Roastery",
    "Medd Cafe & Roastery": "مد", "Microlot Roastery": "Microlot Roastery", "Olala Roastery": "اولالا",
    "Oro Roastery": "أورو", "Osar Roastery": "Osar Roastery", "Palm Roaster": "Palm Roaster", "Peacock Roastery": "Peacock Roastery",
    "Piccolo Roastery": "Piccolo Roastery", "Prob Roastery": "بروب", "PureShell Roastery": "بيور شيل",
    "Qaf Coffee Roasters": "قاف", "Rays Roastery": "ريز", "Roasting House": "بيت التحميص",
    "Seven Grams Roastery": "Seven Grams Roastery", "Shovel Roastery": "شفل", "Sika Roastery": "سيكا",
    "Silverskin Coffee Roasters": "Silverskin Coffee Roasters", "Slope Roastery": "سلوب", "Soil Roastery": "Soil Roastery",
    "Sout Roastery": "Sout Roastery", "Specialty Bean Roastery": "سبيشلتي بين", "Sulalat Coffee": "سلالات",
    "Suwaa Roastery": "صواع", "TRUTH Roastery": "TRUTH Roastery", "The Coffee Factory": "مصنع القهوة",
    "Tricycle Roastery": "ترايسكل", "Woods Roastery": "وودز", "Zelebrity Coffee Roaster": "زليبرتي",
    "dr.CAFE": "dr.CAFE",
}

REGION_AR_EXTRA = {
       "Al-Haymah": "الحيمة", 
       "Bensa": "بنسا",
       
     "Cerrado": "سيرادو",  
     "Gotiti": "قوتيتي",  
    "Jazan": "جازان",  "Kivu": "كيفو",  
     "Loma Poro": "لوما بورو", 
      "Mananasi": "ماناناسي", "Marcala": "ماركالا",
      
     "Oromia": "أوروميا",  "Rakai": "راكاي", "Rovira": "روفيرا",
      "Sertao": "سيرتاو", "Shan": "شان",
     "Thika": "ثيكا",  "Uraga": "أوراغا",
     "Vermelha": "فيرميلا", 
     
}

NOTE_AR_EXTRA = {
    "Black currant": "كشمش أسود", "Cantaloupe": "شمام", "Caramelized": "مكرمل", "Coconut mango": "مانجو وجوز هند",
    "Cotton candy": "غزل البنات", "Crispy wafer": "ويفر مقرمش", "Dried apricot": "مشمش مجفف",
    "Dried cherries": "كرز مجفف", "Green grape": "عنب أخضر", "Green pears": "كمثرى خضراء",
    "Lemon blossom": "زهر الليمون", "Light caramel": "كراميل خفيف", "Lime": "ليم", "Mixed fruits": "فواكه مشكلة",
    "Mixed nuts": "مكسرات مشكلة", "Nectarine": "نكتارين", "Olives": "زيتون", "Orange jam": "مربى برتقال",
    "Orange zest": "قشر برتقال", "Panela sugar": "سكر بانيلا", "Pistachio": "فستق", "Red cherry": "كرز أحمر",
    "Rich cocoa": "كاكاو غني", "Ripe fruit": "فواكه ناضجة", "Soft citrus": "حمضيات ناعمة", "Soft plum": "برقوق ناعم",
    "Stone fruit": "فواكه ذات نواة", "Sweet milk": "حليب حلو", "Sweet orange": "برتقال حلو",
    "Toasted hazelnut": "بندق محمص", "Tropical": "استوائي", "Tropical mango": "مانجو استوائي",
    "Vanilla fudge": "فدج فانيلا", "White tea": "شاي أبيض",
}

# words and phrases inside English coffee names (longest phrases are replaced first)
WORDS_AR = {
    "papua new guinea": "بابوا غينيا الجديدة", "el salvador": "السلفادور", "costa rica": "كوستاريكا",
    "saudi arabia": "السعودية", "single origin": "أحادي المصدر", "passion fruit": "باشن فروت",
    "red fruit": "فواكه حمراء", "cotton candy": "غزل البنات", "wush wush": "ووش ووش", "san marcos": "سان ماركوس",
    "better barista": "بيتر باريستا", "hakuna matata": "هاكونا ماتاتا", "lao xu zhai": "لاو شو تشاي",
    "saudi coffee": "قهوة سعودية", "saudi roast": "تحميص سعودي", "espresso blend": "مزيج اسبريسو",
    "ethiopia": "إثيوبيا", "ethiopian": "إثيوبي", "colombia": "كولومبيا", "colombian": "كولومبي", "brazil": "البرازيل",
    "brazilian": "برازيلي", "yemen": "اليمن", "yemeni": "يمني", "saudi": "سعودي", "kenya": "كينيا", "kenyan": "كيني",
    "uganda": "أوغندا", "ugandan": "أوغندي", "rwanda": "رواندا", "panama": "بنما", "indonesia": "إندونيسيا",
    "guatemala": "غواتيمالا", "peru": "بيرو", "honduras": "هندوراس", "india": "الهند", "nicaragua": "نيكاراغوا",
    "ecuador": "الإكوادور", "china": "الصين", "myanmar": "ميانمار", "java": "جاوة", "bali": "بالي",
    "natural": "مجففة", "washed": "مغسولة", "anaerobic": "لاهوائية", "honey": "عسلية", "decaf": "منزوعة الكافيين",
    "blend": "مزيج", "espresso": "اسبريسو", "filter": "فلتر", "premium": "فاخر", "luxury": "فاخرة",
    "specialty": "مختصة", "speciality": "مختصة", "dark": "داكنة", "light": "فاتحة", "roast": "تحميص",
    "medium": "متوسطة", "crop": "محصول", "fermented": "مخمرة", "style": "ستايل", "original": "أصلي", "lot": "دفعة",
    "vol": "إصدار", "street": "شارع", "lake": "بحيرة", "mountain": "جبل", "mountains": "جبال", "rank": "المرتبة",
    "fruit": "فواكه", "fruity": "فاكهي", "red": "أحمر", "peach": "خوخ", "coconut": "جوز الهند", "orange": "برتقال",
    "watermelon": "بطيخ", "grape": "عنب", "mango": "مانجو", "barley": "شعير", "wafer": "ويفر", "lemonade": "ليمونادة",
    "geisha": "قيشا", "bourbon": "بوربون", "castillo": "كاستيو", "caturra": "كاتورا", "sarchimor": "سارتشيمور",
    "excelso": "إكسلسو", "supremo": "سوبريمو", "finca": "فينكا", "fazenda": "فازيندا", "la": "لا", "el": "إل",
    "san": "سان", "santa": "سانتا", "rosa": "روزا", "flora": "فلورا", "leticia": "ليتيسيا", "morena": "مورينا",
    "carmen": "كارمن", "faysel": "فيصل", "abdosh": "عبدوش", "adolfo": "أدولفو", "marcelo": "مارسيلو", "tima": "تيما",
    "amada": "أمادا", "maria": "ماريا", "perfecta": "بيرفكتا", "thalatheen": "الثلاثين", "shmaisy": "الشميسي",
    "chaffee": "تشافي", "desafinado": "ديسافينادو", "carlos": "كارلوس", "mejia": "ميخيا", "sharqi": "شرقي",
    "frinsa": "فرينسا", "waykan": "وايكان", "ignacio": "إغناسيو", "neom": "نيوم", "khawlan": "خولان",
    "drugar": "دروغار", "baho": "باهو", "tambo": "تامبو", "gasharu": "غاشارو", "siko": "سيكو", "lerida": "ليريدا",
    "amoruso": "أموروسو", "panela": "بانيلا", "sticky": "ستيكي", "pino": "بينو", "alto": "ألتو", "rio": "ريو",
    "dulce": "دولسي", "hashr": "الحشر", "faisal": "فيصل", "abdali": "العبدلي", "vimto": "فيمتو", "holsten": "هولستن",
    "cypress": "سايبرس", "torola": "تورولا", "bodan": "بودان", "budan": "بودان", "yirga": "يرقا",
    "divisadero": "ديفيساديرو", "branca": "برانكا", "jibal": "جبال", "arda": "أردا", "sidama": "سيداما",
    "chelbasa": "تشيلباسا", "kaya": "كايا", "puente": "بوينتي", "fatina": "فاتنة", "amal": "أمل", "assel": "أسيل",
    "dana": "دانة", "lara": "لارا", "linda": "ليندا", "majeda": "ماجدة", "sultana": "سلطانة", "sekary": "سكري",
    "nensebo": "نينسيبو", "modello": "موديلو", "dunga": "دونغا", "hermosa": "هيرموسا", "agustino": "أغوستينو",
    "fresa": "فريسا", "sc": "إس سي", "dairkto": "ديركتو", "cascada": "كاسكادا", "inzovu": "إنزوفو",
    "kiboko": "كيبوكو", "msar": "مسار", "alsail": "السيل", "rancho": "رانتشو", "neiva": "نيفا", "rosita": "روزيتا",
    "keramo": "كيرامو", "gideb": "قيدب", "harw": "هرو", "fahmi": "فهمي", "david": "ديفيد", "banko": "بانكو",
    "taratu": "تاراتو", "manar": "منار", "asilah": "أصيلة", "chella": "تشيلا", "maasai": "ماساي",
    "jaguar": "جاغوار", "aricha": "أريتشا", "apca": "أبكا", "marcos": "ماركوس", "grande": "غراندي",
    "minas": "ميناس", "kitkat": "كيت كات", "barista": "باريستا", "better": "بيتر", "candy": "حلوى",
    "passion": "باشن", "no": "", "coffee": "", "beans": "", "bean": "", "roastery": "", "roaster": "",
    "roasters": "", "the": "", "of": "", "and": "و", "al": "", "brew92": "برو 92",
}

_LATIN = re.compile(r"[A-Za-z]")
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|KG|Kg|kG|g|G|gr|GR|gm)\b")


def _transliterate(word):
    """Last resort for a Latin word we have no entry for (rare)."""
    table = [("sh", "ش"), ("ch", "تش"), ("th", "ث"), ("kh", "خ"), ("gh", "غ"), ("ph", "ف"), ("oo", "و"), ("ee", "ي"),
             ("a", "ا"), ("b", "ب"), ("c", "ك"), ("d", "د"), ("e", "ي"), ("f", "ف"), ("g", "ج"), ("h", "ه"), ("i", "ي"),
             ("j", "ج"), ("k", "ك"), ("l", "ل"), ("m", "م"), ("n", "ن"), ("o", "و"), ("p", "ب"), ("q", "ق"), ("r", "ر"),
             ("s", "س"), ("t", "ت"), ("u", "و"), ("v", "ف"), ("w", "و"), ("x", "كس"), ("y", "ي"), ("z", "ز")]
    w, out = word.lower(), ""
    while w:
        for latin, arabic in table:
            if w.startswith(latin):
                out += arabic
                w = w[len(latin):]
                break
        else:
            w = w[1:]
    return out


def _roaster_forms():
    """Full roaster names and their short forms ("Half World Roastery" -> "Half World")."""
    forms = {}
    for en, ar in ROASTER_AR.items():
        forms[en] = ar
        short = re.sub(r"\b(Coffee Roasters?|Coffee|Roastery|Roasters?|Cafe &)\b", "", en).strip(" &")
        if len(short) >= 3:
            forms.setdefault(short, ar)
    return sorted(forms.items(), key=lambda kv: -len(kv[0]))


ROASTER_FORMS = _roaster_forms()


def _dedupe(text):
    """'لوما بورو لوما بورو' -> 'لوما بورو'"""
    words = text.split()
    for n in (3, 2, 1):
        i = 0
        while i + 2 * n <= len(words):
            if words[i:i + n] == words[i + n:i + 2 * n]:
                del words[i + n:i + 2 * n]
            else:
                i += 1
    return " ".join(words)


def translate_words(text, region_ar, unknown="transliterate"):
    """Turns the Latin parts of a name into Arabic, word by word."""
    text = _SIZE.sub(lambda m: f"{m.group(1)} {'كيلو' if m.group(2).lower() == 'kg' else 'جرام'}", text)
    for en, ar in ROASTER_FORMS:
        text = re.sub(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", ar, text, flags=re.IGNORECASE)
    phrases = {**{k.lower(): v for k, v in region_ar.items()}, **WORDS_AR}
    for en in sorted(phrases, key=len, reverse=True):
        if " " in en:
            text = re.sub(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", phrases[en], text, flags=re.IGNORECASE)

    def word(m):
        w = m.group(0)
        key = w.lower().strip(".'")
        if key in phrases:
            return phrases[key]
        if key.startswith("al-"):
            rest = key[3:]
            return phrases.get(rest, "ال" + _transliterate(rest))
        return _transliterate(w) if unknown == "transliterate" else ""

    text = re.sub(r"[A-Za-z][A-Za-z.'\-]*[A-Za-z.]|[A-Za-z]", word, text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s*([|\-,])\s*(?=[|\-,]|$)", "", text)
    return _dedupe(re.sub(r"\s+", " ", text).strip(" -|,"))


def arabic_coffee_name(english_name, arabic_originals, region_ar):
    """The roaster's own Arabic name when it exists, otherwise the original name as the roaster wrote it.
    We never invent Arabic names."""
    for original in arabic_originals:
        if not original:
            continue
        # drop parts written only in Latin letters ("ألبا | Alba" -> "ألبا")
        parts = re.split(r"\s+[|\-–]\s+", original)
        arabic_parts = [p for p in parts if not (_LATIN.search(p) and not re.search(r"[\u0600-\u06FF]", p))]
        return re.sub(r"\s+", " ", " - ".join(arabic_parts) if arabic_parts else original).strip()
    return english_name
