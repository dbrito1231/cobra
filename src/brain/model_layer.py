"""Model-agnostic LM Studio client per specs/brain/model-layer.md."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from brain.config import BrainConfig


class ModelUnavailableError(Exception):
    """Raised when LM Studio is unreachable and offline mode is not enabled."""

    def __init__(self, message: str, *, cause: str | None = None) -> None:
        super().__init__(message)
        self.cause = cause


@dataclass
class CompletionResult:
    text: str
    model: str
    offline: bool = False


class ModelLayer:
    """Routes inference through LM Studio's OpenAI-compatible REST API."""

    LM_STUDIO_WAIT_MESSAGE = (
        "LM Studio is unreachable. Start LM Studio and load a model, then try again."
    )

    def __init__(self, config: BrainConfig) -> None:
        self.config = config
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def is_available(self) -> bool:
        if self.config.offline_mode:
            return True
        try:
            response = httpx.get(
                f"{self.config.model_endpoint.rstrip('/')}/v1/models",
                timeout=3.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> CompletionResult:
        if self.config.offline_mode:
            return CompletionResult(text=self._offline_response(prompt), model="offline", offline=True)

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model_id or "local-model",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = httpx.post(
                f"{self.config.model_endpoint.rstrip('/')}/v1/chat/completions",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            self._last_error = None
            return CompletionResult(
                text=text,
                model=str(data.get("model", self.config.model_id or "local-model")),
            )
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            self._last_error = str(exc)
            raise ModelUnavailableError(self.LM_STUDIO_WAIT_MESSAGE, cause=str(exc)) from exc

    @staticmethod
    def _offline_response(prompt: str) -> str:
        lowered = prompt.lower()
        if "classify" in lowered or "intent" in lowered:
            return "general"
        if "summarize" in lowered or "summary" in lowered:
            return "Session covered general discussion and follow-ups."
        if "reflect" in lowered or "interview" in lowered:
            return "I understood your answer and captured the key points."
        if "plan" in lowered or "reason" in lowered:
            return (
                "Retrieve relevant wiki pages; use tools if needed; "
                "verify only if claim detected; respond concisely."
            )
        return "I processed your request locally using available context."
