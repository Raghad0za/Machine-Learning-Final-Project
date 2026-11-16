# Vercel entry point: serves the same FastAPI app under /api/...
# Locally you still run:  uvicorn app.main:app --reload   (endpoints without the /api prefix)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402

from app.main import app as coffee_api  # noqa: E402

app = FastAPI(title="Coffee Matchmaker", docs_url=None, redoc_url=None)
app.mount("/api", coffee_api)
