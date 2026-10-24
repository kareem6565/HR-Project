import logging

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes import candidate, cv, evaluate, evaluation, explanation, health, job
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Recruitment AI Service",
    description="CV extraction, embeddings, matching support, and explanation for the AI-assisted recruitment platform.",
    version="0.1.0",
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(cv.router)
app.include_router(evaluate.router)
app.include_router(job.router)
app.include_router(candidate.router)
app.include_router(evaluation.router)
app.include_router(explanation.router)


@app.get("/")
async def root():
    return {"service": "recruitment-ai-service", "status": "running", "provider": settings.llm_provider}
