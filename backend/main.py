import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from soda_agent directory (local dev)
load_dotenv("soda_agent/.env")

# Cloud Run sets GOOGLE_API_KEY via Secret Manager.
# ADK reads from env var directly when available.
if os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_GENAI_USE_VERTEXAI"):
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

from routers.health import router as health_router
from routers.ws_mobile import router as ws_mobile_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="SodaAgent API",
    description="Car voice assistant powered by Gemini Live API and ADK",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ws_mobile_router)


@app.get("/")
async def root():
    return {"service": "SodaAgent", "status": "running", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
