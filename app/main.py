# main.py — الـ API. ما فيه أي منطق ML، يستدعي recommender.py فقط.
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import recommender as rec

app = FastAPI(title="Coffee Matchmaker API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Lang = Literal["ar", "en"]
Focus = Literal["overall", "body", "acidity", "flavor", "price", "origin", "process"]


class Filters(BaseModel):
    max_price_sar: Optional[float] = None
    brew_method: Optional[Literal["espresso", "filter"]] = None
    exclude_infused: bool = False


class RecommendRequest(BaseModel):
    query: str = Field(min_length=1)
    lang: Lang = "ar"
    top_k: int = Field(5, ge=1, le=10)
    filters: Filters = Filters()


class SimilarRequest(BaseModel):
    coffee_id: int
    focus: Focus = "overall"
    lang: Lang = "ar"
    top_k: int = Field(5, ge=1, le=10)
    filters: Filters = Filters()


class ProfileRequest(BaseModel):
    profile_id: int
    lang: Lang = "ar"
    top_k: int = Field(5, ge=1, le=10)
    filters: Filters = Filters()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recommend")
def recommend(req: RecommendRequest):
    return rec.recommend(req.query, req.lang, req.top_k, req.filters.model_dump())


@app.post("/similar")
def similar(req: SimilarRequest):
    try:
        return rec.similar(req.coffee_id, req.focus, req.lang, req.top_k, req.filters.model_dump())
    except KeyError:
        raise HTTPException(404, "coffee_id not found")


@app.get("/coffees")
def coffees(q: str = "", limit: int = 10):
    return rec.search_coffees(q, limit)


@app.get("/profiles")
def profiles(lang: Lang = "ar"):
    return rec.get_profiles(lang)


@app.post("/recommend/profile")
def recommend_profile(req: ProfileRequest):
    try:
        return rec.recommend_by_profile(req.profile_id, req.lang, req.top_k, req.filters.model_dump())
    except KeyError:
        raise HTTPException(404, "profile_id not found")
