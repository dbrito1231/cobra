"""Seed document interview per specs/seed-document/."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from brain.memory.wiki import WikiStore

if TYPE_CHECKING:
    from brain.model_layer import ModelLayer


class InterviewStage(str, Enum):
    COMMUNICATION = "communication"
    DECISION_MAKING = "decision_making"
    VALUES = "values"
    HUMOR = "humor"
    CONTEXT_BEHAVIOR = "context_behavior"


class InterviewPhase(str, Enum):
    """I4–I12 session flow states."""

    ASKING = "asking"
    REFLECTING = "reflecting"
    CONFIRMING = "confirming"
    SUMMARIZING = "summarizing"
    REVIEW = "review"
    APPROVED = "approved"
    STORED = "stored"


STAGE_SECTIONS = {
    InterviewStage.COMMUNICATION: "Communication Style",
    InterviewStage.DECISION_MAKING: "Decision-Making",
    InterviewStage.VALUES: "Values and Beliefs",
    InterviewStage.HUMOR: "Humor and Personality",
    InterviewStage.CONTEXT_BEHAVIOR: "Context-Specific Behavior",
}

STAGE_INTROS = {
    InterviewStage.COMMUNICATION: (
        "Let's start with how you communicate. I'll ask a few questions one at a time."
    ),
    InterviewStage.DECISION_MAKING: (
        "Next, how you make decisions — I'll ask one question at a time."
    ),
    InterviewStage.VALUES: (
        "Now your values and beliefs. Same pace: one question per turn."
    ),
    InterviewStage.HUMOR: (
        "Let's cover humor and personality quirks — one question at a time."
    ),
    InterviewStage.CONTEXT_BEHAVIOR: (
        "Finally, how your tone shifts in different contexts."
    ),
}

STAGE_QUESTIONS = {
    InterviewStage.COMMUNICATION: [
        "How do you prefer people communicate with you — direct or contextual?",
        "Do you prefer short messages or detailed explanations?",
    ],
    InterviewStage.DECISION_MAKING: [
        "When deciding, do you prioritize speed, thoroughness, or consensus?",
        "How do you handle tradeoffs between quality and deadlines?",
    ],
    InterviewStage.VALUES: [
        "What principles guide your decisions most strongly?",
        "What do you consider non-negotiable in how you work?",
    ],
    InterviewStage.HUMOR: [
        "How would you describe your sense of humor?",
        "Any communication quirks or pet peeves I should know?",
    ],
    InterviewStage.CONTEXT_BEHAVIOR: [
        "How does your tone shift between professional and casual settings?",
    ],
}

MVP_STAGES = {
    InterviewStage.COMMUNICATION,
    InterviewStage.DECISION_MAKING,
    InterviewStage.VALUES,
    InterviewStage.HUMOR,
}

_CONFIRM_YES = frozenset(
    {"yes", "y", "yeah", "yep", "correct", "right", "confirm", "confirmed", "that's right", "sounds good"}
)
_CONFIRM_NO = frozenset({"no", "n", "nope", "not quite", "incorrect", "wrong"})
_APPROVE = frozenset(
    {"approve", "approved", "yes", "y", "looks good", "save", "store", "confirm", "ok", "okay"}
)


@dataclass
class InterviewState:
    current_stage: InterviewStage = InterviewStage.COMMUNICATION
    question_index: int = 0
    answers: dict[str, list[str]] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)
    phase: InterviewPhase = InterviewPhase.ASKING
    awaiting_answer: bool = False
    stage_introduced: bool = False
    pending_answer: str = ""
    pending_reflection: str = ""
    pending_summary: str = ""
    last_question: str = ""
    correction_note: str = ""


@dataclass
class SeedTurnResult:
    """Outcome of one seed interview turn for BrainService → WebSocket mapping."""

    events: list[dict[str, object]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    phase: InterviewPhase = InterviewPhase.ASKING
    stage: InterviewStage = InterviewStage.COMMUNICATION
    interview_complete: bool = False
    stored: bool = False


class SeedDocumentManager:
    """Manages staged personality interview and you.md output (I1–I12)."""

    def __init__(
        self,
        wiki: WikiStore,
        state_file: Path,
        model: ModelLayer | None = None,
    ) -> None:
        self.wiki = wiki
        self.state_file = state_file
        self.model = model
        self.state = self._load_state()

    def interview_active(self) -> bool:
        """True while MVP stages are incomplete or a stage flow is in progress."""
        if self.mvp_complete():
            return False
        if self.state.phase in {InterviewPhase.REVIEW, InterviewPhase.SUMMARIZING}:
            return True
        if self.state.awaiting_answer or self.state.stage_introduced:
            return True
        if self.state.completed_stages:
            return True
        if self.state.phase != InterviewPhase.ASKING:
            return True
        return not self.mvp_complete()

    def mvp_complete(self) -> bool:
        completed = {InterviewStage(stage) for stage in self.state.completed_stages}
        return MVP_STAGES.issubset(completed)

    def resume_label(self) -> str:
        section = STAGE_SECTIONS[self.state.current_stage]
        return f"{section} — {self.state.phase.value}"

    def handle_input(self, text: str) -> SeedTurnResult:
        """Route user text through the interview state machine."""

        cleaned = text.strip()
        phase = self.state.phase

        if phase == InterviewPhase.ASKING:
            if not self.state.awaiting_answer:
                return self._open_stage()
            return self._handle_answer(cleaned)
        if phase == InterviewPhase.CONFIRMING:
            return self._handle_confirmation(cleaned)
        if phase == InterviewPhase.REVIEW:
            return self._handle_summary_review(cleaned)
        if phase == InterviewPhase.ASKING or not cleaned:
            return self._open_stage()
        return SeedTurnResult(phase=phase, stage=self.state.current_stage)

    def begin_interview(self) -> SeedTurnResult:
        """I1 — introduce dimension and ask first question without user input."""

        self.state.phase = InterviewPhase.ASKING
        self.state.awaiting_answer = False
        return self._open_stage()

    def next_question(self) -> str | None:
        """Legacy helper — current question if waiting for an answer."""

        if self.state.phase != InterviewPhase.ASKING or not self.state.awaiting_answer:
            return None
        return self._current_question()

    def record_answer(self, answer: str) -> str | None:
        """Legacy helper — process one answer and return next question text if any."""

        if self.state.phase != InterviewPhase.ASKING or not self.state.awaiting_answer:
            self.begin_interview()
        result = self._handle_answer(answer.strip())
        for event in result.events:
            if event.get("type") == "seed_prompt" and event.get("question"):
                return str(event["question"])
        if result.interview_complete:
            return None
        if self.state.phase == InterviewPhase.ASKING and self.state.awaiting_answer:
            return self._current_question()
        return None

    def _open_stage(self) -> SeedTurnResult:
        stage = self.state.current_stage
        section = STAGE_SECTIONS[stage]
        intro = STAGE_INTROS[stage]
        question = self._current_question()
        if not question:
            return self._start_summarizing()

        self.state.stage_introduced = True
        self.state.awaiting_answer = True
        self.state.last_question = question
        self._save_state()

        return SeedTurnResult(
            phase=InterviewPhase.ASKING,
            stage=stage,
            messages=[f"**{section}**\n\n{intro}"],
            events=[
                {
                    "type": "seed_prompt",
                    "stage": section,
                    "phase": InterviewPhase.ASKING.value,
                    "content": intro,
                    "question": question,
                }
            ],
        )

    def _handle_answer(self, answer: str) -> SeedTurnResult:
        stage = self.state.current_stage
        section = STAGE_SECTIONS[stage]
        question = self.state.last_question or self._current_question() or ""

        self.state.pending_answer = answer
        self.state.answers.setdefault(section, []).append(answer)
        self.state.phase = InterviewPhase.REFLECTING
        reflection = self._reflect(answer, question, section)
        self.state.pending_reflection = reflection
        self.state.phase = InterviewPhase.CONFIRMING
        self.state.awaiting_answer = False
        self._save_state()

        confirm_prompt = "Does that capture what you meant? Reply yes to confirm or no to correct."
        return SeedTurnResult(
            phase=InterviewPhase.CONFIRMING,
            stage=stage,
            messages=[reflection, confirm_prompt],
            events=[
                {
                    "type": "seed_confirm",
                    "stage": section,
                    "reflection": reflection,
                    "question": confirm_prompt,
                }
            ],
        )

    def _handle_confirmation(self, text: str) -> SeedTurnResult:
        lowered = text.lower().strip()
        stage = self.state.current_stage
        section = STAGE_SECTIONS[stage]

        if lowered in _CONFIRM_YES:
            self.state.correction_note = ""
            self.state.question_index += 1
            questions = STAGE_QUESTIONS.get(stage, [])
            if self.state.question_index < len(questions):
                self.state.phase = InterviewPhase.ASKING
                self.state.awaiting_answer = False
                self._save_state()
                return self._open_stage()

            return self._start_summarizing()

        if lowered in _CONFIRM_NO:
            self.state.correction_note = ""
            if self.state.answers.get(section):
                self.state.answers[section].pop()
            self.state.phase = InterviewPhase.ASKING
            self.state.awaiting_answer = False
            self._save_state()
            reask = (
                "Thanks for the correction. Let me ask again — "
                f"{self.state.last_question or self._current_question()}"
            )
            self.state.awaiting_answer = True
            self._save_state()
            return SeedTurnResult(
                phase=InterviewPhase.ASKING,
                stage=stage,
                messages=[reask],
                events=[
                    {
                        "type": "seed_prompt",
                        "stage": section,
                        "phase": InterviewPhase.ASKING.value,
                        "content": "Let's try that again with your correction in mind.",
                        "question": self.state.last_question or self._current_question(),
                    }
                ],
            )

        self.state.correction_note = text
        if self.state.answers.get(section):
            self.state.answers[section][-1] = text
        self.state.phase = InterviewPhase.REFLECTING
        reflection = self._reflect(text, self.state.last_question, section)
        self.state.pending_reflection = reflection
        self.state.phase = InterviewPhase.CONFIRMING
        self._save_state()
        confirm_prompt = "Does that capture what you meant now?"
        return SeedTurnResult(
            phase=InterviewPhase.CONFIRMING,
            stage=stage,
            messages=[reflection, confirm_prompt],
            events=[
                {
                    "type": "seed_confirm",
                    "stage": section,
                    "reflection": reflection,
                    "question": confirm_prompt,
                }
            ],
        )

    def _start_summarizing(self) -> SeedTurnResult:
        stage = self.state.current_stage
        section = STAGE_SECTIONS[stage]
        self.state.phase = InterviewPhase.SUMMARIZING
        summary = self._summarize_stage(section)
        self.state.pending_summary = summary
        self.state.phase = InterviewPhase.REVIEW
        self._save_state()

        review_prompt = (
            "Here's my summary for this dimension. Reply approve to save it, "
            "or send edits and I'll revise."
        )
        return SeedTurnResult(
            phase=InterviewPhase.REVIEW,
            stage=stage,
            messages=[summary, review_prompt],
            events=[
                {
                    "type": "seed_summary_review",
                    "stage": section,
                    "summary": summary,
                    "prompt": review_prompt,
                }
            ],
        )

    def _handle_summary_review(self, text: str) -> SeedTurnResult:
        stage = self.state.current_stage
        section = STAGE_SECTIONS[stage]
        lowered = text.lower().strip()

        if lowered in _APPROVE:
            self.state.phase = InterviewPhase.APPROVED
            self._store_stage(section, self.state.pending_summary)
            self.state.phase = InterviewPhase.STORED
            self.state.completed_stages.append(stage.value)
            self._advance_stage()
            self._save_state()

            if self.mvp_complete():
                return SeedTurnResult(
                    phase=InterviewPhase.STORED,
                    stage=stage,
                    stored=True,
                    interview_complete=True,
                    messages=[
                        f"Saved **{section}**. Personality interview complete — thank you!"
                    ],
                )

            next_result = self._open_stage()
            next_result.stored = True
            next_result.messages.insert(
                0, f"Saved **{section}**. Moving to the next dimension."
            )
            return next_result

        self.state.pending_summary = text
        self.state.phase = InterviewPhase.REVIEW
        self._save_state()
        review_prompt = "Updated summary — approve to save or send more edits."
        return SeedTurnResult(
            phase=InterviewPhase.REVIEW,
            stage=stage,
            messages=[text, review_prompt],
            events=[
                {
                    "type": "seed_summary_review",
                    "stage": section,
                    "summary": text,
                    "prompt": review_prompt,
                }
            ],
        )

    def _reflect(self, answer: str, question: str, section: str) -> str:
        if self.model is None:
            return f"For **{section}**, I understood: {answer}"

        from brain.model_layer import ModelUnavailableError

        prompt = (
            f"Interview dimension: {section}\n"
            f"Question: {question}\n"
            f"User answer: {answer}\n\n"
            "Reflect back what you understood in 1-2 sentences. "
            "Do not ask a new question."
        )
        try:
            result = self.model.complete(
                prompt,
                system="You are conducting a personality interview. Be concise and accurate.",
                max_tokens=200,
                temperature=0.2,
            )
            if result.text.strip() and not result.offline:
                return result.text.strip()
        except ModelUnavailableError:
            pass
        return f"For **{section}**, I understood: {answer}"

    def _summarize_stage(self, section: str) -> str:
        answers = self.state.answers.get(section, [])
        joined = " ".join(answers)
        if self.model is None or not joined:
            return joined or f"Summary for {section}."

        from brain.model_layer import ModelUnavailableError

        prompt = (
            f"Dimension: {section}\n"
            f"User answers during interview:\n{joined}\n\n"
            "Write a concise third-person summary for a personality profile wiki page. "
            "2-4 sentences. Facts only from the answers."
        )
        try:
            result = self.model.complete(
                prompt,
                system="Write personality profile summaries. Return only the summary text.",
                max_tokens=300,
                temperature=0.3,
            )
            if result.text.strip() and not result.offline:
                return result.text.strip()
        except ModelUnavailableError:
            pass
        return joined

    def _current_question(self) -> str | None:
        stage = self.state.current_stage
        questions = STAGE_QUESTIONS.get(stage, [])
        if self.state.question_index >= len(questions):
            return None
        return questions[self.state.question_index]

    def _store_stage(self, section: str, summary: str) -> None:
        content = self.wiki.read("you")
        stamp = datetime.now(timezone.utc).date().isoformat()
        if "*Last updated:" in content:
            lines = content.splitlines()
            lines[1] = f"*Last updated: {stamp}*"
            content = "\n".join(lines)
        marker = f"## {section}"
        replacement = f"{marker}\n{summary}\n"
        if marker in content:
            head, tail = content.split(marker, 1)
            rest = tail.split("\n## ", 1)
            if len(rest) == 2:
                content = head + replacement + "\n## " + rest[1]
            else:
                content = head + replacement
        else:
            content += f"\n{replacement}"
        self.wiki.write("you", content)

    def _advance_stage(self) -> None:
        order = list(InterviewStage)
        try:
            index = order.index(self.state.current_stage)
        except ValueError:
            self.state.current_stage = InterviewStage.CONTEXT_BEHAVIOR
        else:
            if index + 1 < len(order):
                self.state.current_stage = order[index + 1]
        self.state.question_index = 0
        self.state.stage_introduced = False
        self.state.awaiting_answer = False
        self.state.pending_answer = ""
        self.state.pending_reflection = ""
        self.state.pending_summary = ""
        self.state.last_question = ""
        self.state.correction_note = ""
        self.state.phase = InterviewPhase.ASKING

    def _load_state(self) -> InterviewState:
        if not self.state_file.exists():
            return InterviewState()
        import json

        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            stage_raw = data.get("current_stage", InterviewStage.COMMUNICATION.value)
            if isinstance(stage_raw, int):
                order = list(InterviewStage)
                stage = order[stage_raw - 1] if 1 <= stage_raw <= len(order) else InterviewStage.COMMUNICATION
            else:
                stage = InterviewStage(stage_raw)
            completed_raw = data.get("completed_stages", [])
            completed_stages: list[str] = []
            order = list(InterviewStage)
            for item in completed_raw:
                if isinstance(item, int) and 1 <= item <= len(order):
                    completed_stages.append(order[item - 1].value)
                else:
                    completed_stages.append(str(item))
            phase_raw = data.get("phase", InterviewPhase.ASKING.value)
            return InterviewState(
                current_stage=stage,
                question_index=int(data.get("question_index", 0)),
                answers=data.get("answers", {}),
                completed_stages=completed_stages,
                phase=InterviewPhase(phase_raw),
                awaiting_answer=bool(data.get("awaiting_answer", False)),
                stage_introduced=bool(data.get("stage_introduced", False)),
                pending_answer=str(data.get("pending_answer", "")),
                pending_reflection=str(data.get("pending_reflection", "")),
                pending_summary=str(data.get("pending_summary", "")),
                last_question=str(data.get("last_question", "")),
                correction_note=str(data.get("correction_note", "")),
            )
        except (json.JSONDecodeError, ValueError):
            return InterviewState()

    def _save_state(self) -> None:
        import json

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_stage": self.state.current_stage.value,
            "question_index": self.state.question_index,
            "answers": self.state.answers,
            "completed_stages": self.state.completed_stages,
            "phase": self.state.phase.value,
            "awaiting_answer": self.state.awaiting_answer,
            "stage_introduced": self.state.stage_introduced,
            "pending_answer": self.state.pending_answer,
            "pending_reflection": self.state.pending_reflection,
            "pending_summary": self.state.pending_summary,
            "last_question": self.state.last_question,
            "correction_note": self.state.correction_note,
        }
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
