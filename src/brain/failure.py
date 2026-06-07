"""Failure handling per specs/brain/failure-handling.md."""

from __future__ import annotations

from brain.models import PipelineResult


class FailureHandler:
    """CHECK → FINAL or FAIL branches after synthesis."""

    def finalize(self, result: PipelineResult) -> str:
        if result.can_answer and result.synthesized.strip():
            return result.personality_filtered or result.synthesized

        suggestions = result.failure_suggestions or [
            "Check official documentation for the topic.",
            "Search trusted references or ask a subject-matter expert.",
            "Rephrase the question with more specific constraints.",
        ]
        lines = [
            "I don't know based on what I have locally, but here's where I'd look:",
            "",
        ]
        for index, suggestion in enumerate(suggestions, start=1):
            lines.append(f"{index}. {suggestion}")
        return "\n".join(lines)
