# ☕ مَذاق (Mathaq)

Not sure which specialty coffee to buy? Tell us what you like in your own words, or pick a coffee you loved, and we recommend the 5 closest beans out of 569 coffees from 71 Saudi roasters.

The deployed site is one page with two parts: an Arabic **presentation** (13 slides) and a live **demo** that calls the real model. The demo also shows *how* the model decided (the "كيف اختار؟" panel).

## Problem
Specialty coffee buyers in Saudi Arabia face hundreds of beans described in different languages and formats, with many missing details (70% have no body level, 7% have no tasting notes). It's hard to know what a bag will taste like before buying.

## Solution
Three ways to ask:
- **Free text** (Arabic or English): "أبي شي فاكهي للفلتر بأقل من 70 ريال"
- **A coffee you liked** + what you liked about it (body, acidity, bitterness, flavor, price, origin, process)
- **A coffee personality** card for beginners

## Notebooks (run in this order)
| Notebook | Author | What it does |
|---|---|---|
| `Coffee_EDA.ipynb` | Ruba | Cleaning and EDA, saves `data/saudi_specialty_coffee_beans_clean.csv` |
| `02_Modeling.ipynb` | Raghad | Flavor and body models (GroupKFold by roaster), taste scores for acidity, body and bitterness, saves `data/coffee_enriched.csv` and `models/flavor_model.joblib` |
| `03_Clustering.ipynb` | Raghad | K-Means vs Agglomerative clustering of taste profiles (analysis; the app uses the 6 profiles from notebook 04) |
| `04_Recommender_KNN.ipynb` | Omar | The app's models: flavor and body models, K-Means personalities, the KNN recommender, its tuning and tests. Saves `models/` and `data/app_coffees.csv` |
| `05_Evaluation.ipynb` | Daniyah | Independent evaluation of the app's engine: 31 test requests, constraint checks, leave-one-out similarity, blind human test |

## Models
| Part | Type | Role |
|---|---|---|
| **K-Nearest Neighbors** (cosine) | Unsupervised | The recommender. Every coffee is a point made of 8 blocks (tasting notes TF-IDF, flavor families, body, acidity, bitterness, process, origin, price). The request becomes a point in the same space and we return the 5 closest coffees. |
| Random Forest (multi-label) | Supervised | Predicts the flavor families of the 42 coffees with no notes. Compared with Logistic Regression and Gradient Boosting. |
| Random Forest (3 classes) | Supervised | Predicts body for the 397 coffees without it. Its probabilities feed the KNN body block. |
| KNNImputer | Unsupervised | Fills the notes of the 42 coffees from their 10 nearest coffees. |
| K-Means (k = 6) | Unsupervised | Groups the coffees into 6 personality cards. |
| Acidity and bitterness | Taste scores (02_Modeling) | The roaster's stated value, otherwise an estimated level from a score checked with Spearman. |
| Arabic understanding | Rules | A phrase matcher with typo tolerance. |

Why KNN and not a supervised recommender: the data has no ratings or purchases ("user X liked coffee Y"), so there is no target to train on.

## Results
| Metric                                     | Result   | Baseline                |
|:-------------------------------------------|:---------|:------------------------|
| Requests understood correctly (of 31)      | 94%      | —                       |
| Constraint satisfaction                    | 100%     | —                       |
| Constraint satisfaction (real values only) | 100%     | —                       |
| Leave-one-out precision@5                  | 0.98     | 5 random coffees: 0.35  |
| Blind test mean rating (1–5)               | pending  | random coffees: pending |
| Test | Result |
|---|---|
| Held-out requests fully understood (notebook 04) | **22 / 22** |
| Precision@5 on held-out requests (KNN / keyword search / random) | **0.95** / 0.34 / 0.20 |
| Arabic requests: KNN vs keyword search | **0.98** vs 0.17 |
| "Something like X" + focus (held-out coffees): same origin / process / price or cheaper / body | 99% / 98% / 100% / 86% |
| Independent test by Daniyah (31 requests, notebook 05): understood on the first try | **77%** (misses were bitterness and English typos, now added) |
| Leave-one-out "similar coffees" precision@5 (notebook 05) | **0.77** vs 0.35 random |
| Speed | about 9 ms per request |

KNN settings were chosen with tuning data only (development requests and 50 tuning coffees), then reported on held-out requests and other coffees.

## Project structure
| Path | Contents |
|---|---|
| `notebooks/` | The five notebooks above, plus `arabic_display.py` (Arabic display names) |
| `app/recommender.py` | The recommender used by the API (numpy only, same math as notebook 04) |
| `app/main.py` | FastAPI app (6 endpoints) |
| `api/index.py` | Serves the FastAPI app under `/api` (used locally and on Vercel) |
| `try_recommender.py` | Try the recommender from the terminal |
| `data/` | Raw, clean and enriched data, the translation table and the test requests |
| `models/` | `knn_index.npz` + `knn_meta.json` (the KNN space), `profiles.json`, `lexicon.json`, `report.json`, and the trained `.joblib` models |
| `frontend/` | React (Vite) presentation + demo, fully in Arabic |

## Run locally
API:

    pip install -r requirements.txt
    uvicorn api.index:app --reload --port 8000

API docs: http://127.0.0.1:8000/api/docs

Frontend (in a second terminal):

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173 (the dev server forwards `/api` to port 8000).

Try it from the terminal:

    python try_recommender.py "ابغى محصول مرارته عالية"

Re-run the notebooks (needs `requirements-notebook.txt`) in the order above.

## API
| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | status |
| POST | `/api/recommend` | free-text request |
| POST | `/api/similar` | coffees similar to a coffee, with a focus |
| POST | `/api/recommend/profile` | top coffees of a personality |
| GET | `/api/coffees?q=` | search coffee names (for the "liked a coffee" box) |
| GET | `/api/profiles` | the 6 personality cards |

Responses include `status` (ok / clarify / no_results), `results` and `reasons`. Text and similar answers also include an `explain` object used by the "how it decided" panel.

## Team
- Ruba Alotaibi: data cleaning and EDA
- Raghad Alasmari: modeling
- Daniyah AlEid: evaluation
- Omar Alshuail: recommender and deployment
