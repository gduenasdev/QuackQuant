from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/agents/model-providers")
def model_providers() -> dict[str, object]:
    settings = get_settings()
    return {
        "active": settings.llm_provider,
        "model": settings.llm_model,
        "providers": [
            {
                "id": "none",
                "label": "No LLM",
                "role": "Deterministic scanner math only",
                "available": True,
            },
            {
                "id": "ollama",
                "label": "Ollama",
                "role": "Optional local explanations, summaries, and agent review",
                "available": bool(settings.ollama_base_url),
                "base_url": settings.ollama_base_url,
            },
            {
                "id": "openai",
                "label": "OpenAI",
                "role": "Optional hosted explanations, summaries, and agent review",
                "available": settings.llm_provider == "openai",
            },
        ],
        "scanner_dependency": "Signals, paper fills, stops, targets, and performance stats are deterministic math and do not require an LLM.",
    }
