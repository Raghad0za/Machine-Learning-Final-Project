# ☕ Coffee Matchmaker

Not sure which specialty coffee to buy? Tell us what you like, in your own words or by picking a coffee you loved, and we recommend the closest beans from 569 coffees across 71 Saudi roasters.

## Problem
Specialty coffee drinkers in Saudi Arabia face hundreds of beans with inconsistent, often missing tasting notes, so it's hard to know what a bag will taste like before buying.

## Solution
- **Free-text search:** "I want something fruity for V60 under 70 SAR"
- **Similar coffee:** "I liked the body of Colombia Huila, what's similar?"
- **Beginner mode:** pick a coffee personality

## Data
Collected by web scraping Saudi roaster websites and the Qavashop marketplace (569 coffees, 71 roasters).

## Project structure
| Folder | Contents |
|---|---|
| `app/` | FastAPI app and recommender |
| `data/` | Cleaned and enriched datasets |
| `models/` | Trained models (.joblib) |
| `frontend/` | User interface |
| `notebooks/` | EDA, modeling and evaluation |

## Run locally
    pip install -r requirements.txt
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs

## Results
_Coming soon._

## Team
- Ruba Alotaibi: data cleaning and EDA
- Raghad Alasmari: modeling
- Daniyah AlEid: evaluation
- Omar Alshuail: deployment
