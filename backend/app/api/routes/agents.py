from fastapi import APIRouter

from app.api.todos import not_implemented
from app.config import get_settings
from app.schemas import AgentRunCreate

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


@router.post("/agents/{agent_id}/runs", status_code=202)
def create_agent_run(agent_id: str, payload: AgentRunCreate) -> None:
    # TODO: Allow only research/paper modes until live-trading controls are independently reviewed.
    # TODO: Snapshot prompts, tools, model, strategy, inputs, and risk-policy versions.
    not_implemented("Persist an auditable paper/research run and enqueue it.")


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> None:
    # TODO: Return authorized state without leaking internal prompts, secrets, or stack traces.
    not_implemented("Return sanitized, ownership-scoped run state.")


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str) -> None:
    # TODO: Record cancellation intent; teach workers to stop safely at checkpoints.
    not_implemented("Persist cancellation intent and stop safely at a checkpoint.")


@router.get("/runs/{run_id}/events")
def run_events(run_id: str) -> None:
    # TODO: Implement authenticated Server-Sent Events with heartbeat and resume IDs.
    not_implemented("Stream authorized run updates using Server-Sent Events.")


@router.get("/runs/{run_id}/decisions")
def run_decisions(run_id: str) -> None:
    # TODO: Return append-only decisions, inputs, policy checks, and outcomes.
    not_implemented("Expose an immutable, redacted decision audit trail.")
