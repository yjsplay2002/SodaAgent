from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ClaudeCodeRunResult:
    exit_code: int
    working_directory: str
    duration_ms: int
    result_text: str
    stdout: str
    stderr: str
    session_id: str | None
    total_cost_usd: float | None
    raw_output: dict[str, Any] | None

    @property
    def status(self) -> str:
        return "completed" if self.exit_code == 0 else "failed"


class ClaudeCodeService:
    def __init__(self) -> None:
        self.binary = os.getenv("CLAUDE_CODE_BIN", "claude")
        self.workspace_root = Path(
            os.getenv(
                "CLAUDE_CODE_WORKSPACE_ROOT",
                Path(__file__).resolve().parents[2],
            )
        ).resolve()
        self.timeout_seconds = int(os.getenv("CLAUDE_CODE_TIMEOUT_SECONDS", "600"))
        self.permission_mode = os.getenv(
            "CLAUDE_CODE_PERMISSION_MODE",
            "bypassPermissions",
        )
        self.default_model = os.getenv("CLAUDE_CODE_MODEL")
        self.default_system_prompt = os.getenv(
            "CLAUDE_CODE_SYSTEM_PROMPT",
            (
                "You are running inside SodaAgent's server-side Claude Code "
                "executor. Work only inside the provided repository and finish "
                "by summarizing the concrete code changes and verification "
                "results."
            ),
        )
        raw_allowed_tools = os.getenv("CLAUDE_CODE_ALLOWED_TOOLS", "").strip()
        self.default_allowed_tools = [
            item.strip() for item in raw_allowed_tools.split(",") if item.strip()
        ]

    def resolve_working_directory(self, working_directory: str | None) -> Path:
        requested = (working_directory or ".").strip() or "."
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = (self.workspace_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError(
                "working_directory must stay inside the configured workspace root"
            ) from exc

        if not candidate.exists() or not candidate.is_dir():
            raise FileNotFoundError(f"working_directory does not exist: {candidate}")

        return candidate

    def build_command(
        self,
        prompt: str,
        *,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        append_system_prompt: str | None = None,
        max_budget_usd: float | None = None,
    ) -> list[str]:
        command = [
            self.binary,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--no-session-persistence",
            "--add-dir",
            str(self.workspace_root),
        ]

        if self.permission_mode:
            command.extend(["--permission-mode", self.permission_mode])

        selected_model = model or self.default_model
        if selected_model:
            command.extend(["--model", selected_model])

        selected_tools = allowed_tools or self.default_allowed_tools
        if selected_tools:
            command.extend(["--allowedTools", ",".join(selected_tools)])

        system_prompt_parts = [self.default_system_prompt]
        if append_system_prompt:
            system_prompt_parts.append(append_system_prompt.strip())
        system_prompt = "\n\n".join(
            part for part in system_prompt_parts if part and part.strip()
        )
        if system_prompt:
            command.extend(["--append-system-prompt", system_prompt])

        if max_budget_usd is not None:
            command.extend(["--max-budget-usd", str(max_budget_usd)])

        return command

    async def get_status(self) -> dict[str, Any]:
        binary_path = shutil.which(self.binary)
        version = await self._run_metadata_command([self.binary, "--version"])
        auth_status = await self._run_metadata_command(
            [self.binary, "auth", "status"]
        )

        return {
            "installed": binary_path is not None,
            "binary": self.binary,
            "binary_path": binary_path,
            "workspace_root": str(self.workspace_root),
            "permission_mode": self.permission_mode,
            "default_model": self.default_model,
            "configured_auth": auth_status["exit_code"] == 0
            or bool(os.getenv("ANTHROPIC_API_KEY"))
            or bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN"))
            or bool(os.getenv("CLAUDE_CODE_USE_BEDROCK"))
            or bool(os.getenv("CLAUDE_CODE_USE_VERTEX")),
            "version": version["stdout"].strip() or None,
            "auth_status": auth_status["stdout"].strip() or auth_status["stderr"].strip(),
        }

    async def run(
        self,
        *,
        prompt: str,
        working_directory: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        append_system_prompt: str | None = None,
        max_budget_usd: float | None = None,
    ) -> ClaudeCodeRunResult:
        binary_path = shutil.which(self.binary)
        if not binary_path:
            raise RuntimeError(f"Claude Code binary not found: {self.binary}")

        target_directory = self.resolve_working_directory(working_directory)
        command = self.build_command(
            prompt,
            model=model,
            allowed_tools=allowed_tools,
            append_system_prompt=append_system_prompt,
            max_budget_usd=max_budget_usd,
        )

        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(target_directory),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise TimeoutError(
                f"Claude Code timed out after {self.timeout_seconds} seconds"
            ) from exc

        duration_ms = int((time.monotonic() - start) * 1000)
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        parsed_output = self._parse_json_output(stdout_text)

        return ClaudeCodeRunResult(
            exit_code=process.returncode or 0,
            working_directory=str(target_directory),
            duration_ms=duration_ms,
            result_text=self._extract_result_text(
                parsed_output,
                fallback=stdout_text if process.returncode == 0 else stderr_text or stdout_text,
            ),
            stdout=stdout_text,
            stderr=stderr_text,
            session_id=self._extract_string(parsed_output, "session_id"),
            total_cost_usd=self._extract_float(parsed_output, "total_cost_usd"),
            raw_output=parsed_output,
        )

    async def _run_metadata_command(self, command: list[str]) -> dict[str, Any]:
        binary_path = shutil.which(self.binary)
        if not binary_path:
            return {"exit_code": 127, "stdout": "", "stderr": "binary not found"}

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
        stdout, stderr = await process.communicate()
        return {
            "exit_code": process.returncode or 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }

    @staticmethod
    def _parse_json_output(output: str) -> dict[str, Any] | None:
        if not output:
            return None

        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None

        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _extract_result_text(
        payload: dict[str, Any] | None,
        *,
        fallback: str,
    ) -> str:
        if payload:
            for key in ("result", "text", "message", "output"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            content = payload.get("content")
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            texts.append(text.strip())
                if texts:
                    return "\n\n".join(texts)

        return fallback.strip() or "Claude Code returned no output."

    @staticmethod
    def _extract_string(
        payload: dict[str, Any] | None,
        key: str,
    ) -> str | None:
        if not payload:
            return None
        value = payload.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _extract_float(
        payload: dict[str, Any] | None,
        key: str,
    ) -> float | None:
        if not payload:
            return None
        value = payload.get(key)
        return float(value) if isinstance(value, (int, float)) else None


claude_code_service = ClaudeCodeService()
