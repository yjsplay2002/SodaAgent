from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.claude_code_service import claude_code_service

router = APIRouter(prefix="/api/code/claude", tags=["claude-code"])


class ClaudeCodeRunRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=20000)
    working_directory: str = Field(default=".")
    model: str | None = None
    allowed_tools: list[str] | None = None
    append_system_prompt: str | None = Field(default=None, max_length=4000)
    max_budget_usd: float | None = Field(default=None, gt=0)


class ClaudeCodeRunResponse(BaseModel):
    status: str
    exit_code: int
    working_directory: str
    duration_ms: int
    result_text: str
    stderr: str | None = None
    session_id: str | None = None
    total_cost_usd: float | None = None
    raw_output: dict[str, Any] | None = None


@router.get("/status")
async def get_claude_code_status():
    return await claude_code_service.get_status()


@router.post("/run", response_model=ClaudeCodeRunResponse)
async def run_claude_code_task(request: ClaudeCodeRunRequest):
    try:
        result = await claude_code_service.run(
            prompt=request.prompt,
            working_directory=request.working_directory,
            model=request.model,
            allowed_tools=request.allowed_tools,
            append_system_prompt=request.append_system_prompt,
            max_budget_usd=request.max_budget_usd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ClaudeCodeRunResponse(
        status=result.status,
        exit_code=result.exit_code,
        working_directory=result.working_directory,
        duration_ms=result.duration_ms,
        result_text=result.result_text,
        stderr=result.stderr or None,
        session_id=result.session_id,
        total_cost_usd=result.total_cost_usd,
        raw_output=result.raw_output,
    )
