"""Verification pipeline V1–V10 per specs/brain/verification-pipeline.md."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from brain.config import BrainConfig
from brain.models import VerificationOutcome
from brain.privacy import PrivacyGate, sanitize_topic
from brain.wiki_ops import WikiOperations


class VerificationPipeline:
    """Fact-checks verifiable claims with 2-source minimum agreement."""

    def __init__(
        self,
        config: BrainConfig,
        privacy: PrivacyGate,
        wiki_ops: WikiOperations,
        *,
        mcp_call=None,
        audit_outbound: Callable[..., None] | None = None,
    ) -> None:
        self.config = config
        self.privacy = privacy
        self.wiki_ops = wiki_ops
        self._mcp_call = mcp_call
        self._audit_outbound = audit_outbound

    async def verify(self, claim: str) -> tuple[VerificationOutcome, str]:
        sanitized = sanitize_topic(claim)
        decision = await self.privacy.screen_outbound(
            "verification",
            sanitized,
            reason="Fact-check requires external sources.",
        )
        if not decision.allowed:
            return VerificationOutcome.SUPPRESSED, "Verification blocked by privacy gate."

        sources: dict[str, str] = {}
        for name, fetcher in (
            ("claude", self._query_claude),
            ("copilot", self._query_copilot),
            ("mcp", self._query_mcp),
        ):
            answer = await fetcher(decision.sanitized_query)
            if answer:
                sources[name] = answer

        if len(sources) < 2:
            self.wiki_ops.store_non_finding(sanitized)
            return VerificationOutcome.SUPPRESSED, "Fewer than two sources responded."

        values = list(sources.values())
        normalized = [value.lower().strip() for value in values]
        if all(value == normalized[0] for value in normalized):
            detail = f"Verified: {values[0]} (sources: {', '.join(sources)})"
            self.wiki_ops.store_verified_fact(claim, list(sources.keys()))
            return VerificationOutcome.CORRECTION, detail

        conflict = "; ".join(f"{name}: {text}" for name, text in sources.items())
        return VerificationOutcome.CONFLICT, f"Sources conflict — {conflict}"

    async def _query_claude(self, query: str) -> str:
        destination = "https://api.anthropic.com"
        if not self.config.claude_api_key:
            return ""
        try:
            response = httpx.post(
                f"{destination}/v1/messages",
                headers={
                    "x-api-key": self.config.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-latest",
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": query}],
                },
                timeout=self.config.verification_timeout_seconds,
            )
            self._audit_verification_call(
                destination,
                query,
                success=response.status_code == 200,
            )
            if response.status_code != 200:
                return ""
            data = response.json()
            return data["content"][0]["text"].strip()
        except httpx.HTTPError:
            self._audit_verification_call(destination, query, success=False)
            return ""

    async def _query_copilot(self, query: str) -> str:
        destination = "https://api.githubcopilot.com"
        if not self.config.copilot_api_key:
            return ""
        try:
            response = httpx.post(
                f"{destination}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.copilot_api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 256,
                },
                timeout=self.config.verification_timeout_seconds,
            )
            self._audit_verification_call(
                destination,
                query,
                success=response.status_code == 200,
            )
            if response.status_code != 200:
                return ""
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPError:
            self._audit_verification_call(destination, query, success=False)
            return ""

    def _audit_verification_call(
        self,
        destination: str,
        query: str,
        *,
        success: bool,
    ) -> None:
        if self._audit_outbound is None:
            return
        from security.models import ApprovalStatus, RequestOutcome

        self._audit_outbound(
            destination,
            query,
            trigger="verification",
            approval_status=ApprovalStatus.AUTO,
            outcome=RequestOutcome.SUCCESS if success else RequestOutcome.FAILURE,
        )

    async def _query_mcp(self, query: str) -> str:
        if self._mcp_call is None:
            return ""
        try:
            result = await self._mcp_call("web_search", query)
            if result.success and result.response:
                return str(result.response)[:500]
        except Exception:
            return ""
        return ""
