"""Seed document interview per specs/seed-document/."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from brain.memory.wiki import WikiStore
from brain.model_layer import ModelUnavailableError

if TYPE_CHECKING:
    from brain.living_document import LivingDocumentManager
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


class InterviewKind(str, Enum):
    SEED = "seed"
    PE2_REFRESH = "pe2_refresh"


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
        "How do you naturally write and speak? (formal, casual, direct, verbose)",
        "How do you open conversations vs. close them?",
        "Do you prefer short answers or thorough explanations?",
        "How do you adjust your tone for different audiences?",
        "What phrases or words do you use often?",
        "What communication habits do you dislike in others?",
    ],
    InterviewStage.DECISION_MAKING: [
        "How do you approach a big decision?",
        "Do you gather all information first, or decide with what you have?",
        "How do you handle uncertainty?",
        "Do you prefer reversible or irreversible decisions and why?",
        "How do you weigh logic vs. intuition?",
        "How do you handle being wrong about a decision?",
    ],
    InterviewStage.VALUES: [
        "What are your non-negotiables — things you will never compromise on?",
        "What do you stand for professionally? Personally?",
        "What do you believe that most people disagree with?",
        "How do you treat people who are rude to you?",
        "What makes someone earn your trust?",
        "What causes you to lose trust in someone?",
    ],
    InterviewStage.HUMOR: [
        "How would you describe your sense of humor?",
        "What do you find genuinely funny vs. annoying in humor?",
        "What are your biggest pet peeves?",
        "How do you act when you're stressed vs. when you're relaxed?",
        "How do you handle conflict with people you respect?",
        "What do people consistently misunderstand about you?",
    ],
    InterviewStage.CONTEXT_BEHAVIOR: [
        "How does your tone shift between professional, casual, and close relationships?",
        "How do you like to receive feedback?",
        "What is your relationship with failure?",
        "When are you most productive, and what drains your energy?",
        "What opinions do you hold on topics you frequently discuss?",
        "What habits and routines define your day?",
    ],
}

MVP_STAGES = {
    InterviewStage.COMMUNICATION,
    InterviewStage.DECISION_MAKING,
    InterviewStage.VALUES,
    InterviewStage.HUMOR,
}

PE2_QUESTIONS: dict[str, list[str]] = {
    "Communication Style": [
        "Has your communication style changed since we last talked?",
        "Are there situations where you communicate differently now?",
        "Anything you'd add or correct about how you come across?",
    ],
    "Decision-Making": [
        "Has your approach to decisions shifted recently?",
        "Are there decisions you're handling differently now?",
        "What would you update about how you make tradeoffs?",
    ],
    "Values and Beliefs": [
        "Have any of your core values or beliefs evolved?",
        "Is there something you stand for more strongly now?",
        "What would you refine about your non-negotiables?",
    ],
    "Humor and Personality": [
        "Has your sense of humor or personality shifted?",
        "Any new pet peeves or quirks I should know?",
        "What do people still misunderstand about you?",
    ],
    "Context-Specific Behavior": [
        "Has your tone in different contexts changed?",
        "How do you handle feedback differently now?",
        "What habits or energy patterns have shifted?",
    ],
}

SECTION_TO_STAGE = {value: key for key, value in STAGE_SECTIONS.items()}

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
    optional_interview_active: bool = False
    session_active: bool = False
    interview_kind: str = InterviewKind.SEED.value
    pe2_section: str = ""
    pe2_refresh_active: bool = False
    active_questions: list[str] = field(default_factory=list)
    pe2_last_at: dict[str, str] = field(default_factory=dict)
    last_pe2_prompt_at: str = ""
    last_mv3_prompt_at: str = ""
    overrides: dict[str, dict[str, str]] = field(default_factory=dict)


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
        living_doc: LivingDocumentManager | None = None,
    ) -> None:
        self.wiki = wiki
        self.state_file = state_file
        self.model = model
        self.living_doc = living_doc
        self.state = self._load_state()

    def set_living_doc(self, living_doc: LivingDocumentManager) -> None:
        self.living_doc = living_doc

    def interview_active(self) -> bool:
        """True while an interview session is in progress (seed, optional S5, or PE2)."""
        if self.state.session_active:
            return True
        if self._optional_interview_in_progress():
            return True
        if self._pe2_interview_in_progress():
            return True
        if self.state.phase in {InterviewPhase.REVIEW, InterviewPhase.SUMMARIZING}:
            return True
        if self.state.awaiting_answer or self.state.stage_introduced:
            return True
        if self.state.phase not in {InterviewPhase.ASKING, InterviewPhase.STORED}:
            return True
        return False

    def needs_seed_gate(self) -> bool:
        """First-run hard gate: all stages S1–S5 must be stored."""
        return not self.profile_complete()

    def mvp_complete(self) -> bool:
        completed = {InterviewStage(stage) for stage in self.state.completed_stages}
        return MVP_STAGES.issubset(completed)

    def profile_complete(self) -> bool:
        completed = {InterviewStage(stage) for stage in self.state.completed_stages}
        return set(InterviewStage) == completed

    def optional_stages_remaining(self) -> bool:
        return InterviewStage.CONTEXT_BEHAVIOR.value not in self.state.completed_stages

    def _optional_interview_in_progress(self) -> bool:
        if not self.optional_stages_remaining():
            return False
        if not self.state.optional_interview_active:
            return False
        if self.state.current_stage != InterviewStage.CONTEXT_BEHAVIOR:
            return False
        if self.state.phase in {InterviewPhase.REVIEW, InterviewPhase.SUMMARIZING}:
            return True
        if self.state.awaiting_answer or self.state.stage_introduced:
            return True
        if self.state.phase != InterviewPhase.ASKING:
            return True
        return self.state.optional_interview_active

    def _pe2_interview_in_progress(self) -> bool:
        if not self.state.pe2_refresh_active:
            return False
        if self.state.phase in {InterviewPhase.REVIEW, InterviewPhase.SUMMARIZING}:
            return True
        if self.state.awaiting_answer or self.state.stage_introduced:
            return True
        if self.state.phase != InterviewPhase.ASKING:
            return True
        return self.state.pe2_refresh_active

    def stalest_pe2_section(self) -> str | None:
        if not self.mvp_complete():
            return None
        sections = list(PE2_QUESTIONS.keys())
        never = [s for s in sections if s not in self.state.pe2_last_at]
        if never:
            return never[0]
        oldest = min(
            sections,
            key=lambda s: self.state.pe2_last_at.get(s, ""),
        )
        return oldest

    def should_prompt_pe2(self) -> bool:
        if not self.profile_complete():
            return False
        if self.state.pe2_refresh_active or self.state.session_active:
            return False
        if not self.state.last_pe2_prompt_at:
            return True
        try:
            last = datetime.fromisoformat(self.state.last_pe2_prompt_at)
        except ValueError:
            return True
        return (datetime.now(timezone.utc) - last).days >= 7

    def record_pe2_prompt(self) -> None:
        self.state.last_pe2_prompt_at = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def begin_optional_interview(self) -> SeedTurnResult:
        """Start or resume Stage 5 without blocking normal chat when idle."""

        if not self.mvp_complete():
            return self.begin_interview()
        if self.profile_complete():
            return SeedTurnResult(
                phase=InterviewPhase.STORED,
                stage=InterviewStage.CONTEXT_BEHAVIOR,
                interview_complete=True,
                messages=["Your personality profile is already complete."],
            )
        self.state.current_stage = InterviewStage.CONTEXT_BEHAVIOR
        self.state.optional_interview_active = True
        self.state.session_active = True
        self.state.interview_kind = InterviewKind.SEED.value
        self.state.active_questions = []
        self.state.phase = InterviewPhase.ASKING
        self.state.awaiting_answer = False
        self.state.stage_introduced = False
        self._save_state()
        return self._open_stage()

    def begin_pe2_refresh(self, section: str) -> SeedTurnResult:
        """PE2 — refresh an existing dimension with follow-up questions."""

        if not self.mvp_complete():
            return SeedTurnResult(
                messages=["Complete the initial personality interview before a refresh."],
            )
        questions = PE2_QUESTIONS.get(section)
        if not questions:
            return SeedTurnResult(messages=[f"Unknown dimension: {section}"])

        stage = SECTION_TO_STAGE.get(section)
        if stage is None:
            return SeedTurnResult(messages=[f"Unknown dimension: {section}"])

        existing = self.read_section(section)
        self.state.current_stage = stage
        self.state.pe2_section = section
        self.state.pe2_refresh_active = True
        self.state.session_active = True
        self.state.interview_kind = InterviewKind.PE2_REFRESH.value
        self.state.active_questions = list(questions)
        self.state.question_index = 0
        self.state.phase = InterviewPhase.ASKING
        self.state.awaiting_answer = False
        self.state.stage_introduced = False
        self.state.answers.pop(section, None)
        self._save_state()
        intro = (
            f"Let's refresh **{section}**. I'll ask a few follow-up questions "
            f"one at a time.\n\nCurrent profile:\n{existing[:400]}"
        )
        return self._open_stage(intro_override=intro)

    def end_optional_interview(self) -> None:
        self.state.optional_interview_active = False
        self._end_session()

    def _end_session(self) -> None:
        self.state.session_active = False
        self.state.pe2_refresh_active = False
        self.state.interview_kind = InterviewKind.SEED.value
        self.state.active_questions = []
        self.state.pe2_section = ""
        self.state.phase = InterviewPhase.ASKING
        self.state.awaiting_answer = False
        self.state.stage_introduced = False
        self._save_state()

    def _active_section(self) -> str:
        if self.state.interview_kind == InterviewKind.PE2_REFRESH.value and self.state.pe2_section:
            return self.state.pe2_section
        return STAGE_SECTIONS[self.state.current_stage]

    def record_mv3_prompt(self) -> None:
        self.state.last_mv3_prompt_at = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def should_prompt_mv3(self) -> bool:
        if not self.mvp_complete() or not self.optional_stages_remaining():
            return False
        if self.state.optional_interview_active:
            return False
        if not self.state.last_mv3_prompt_at:
            return True
        try:
            last = datetime.fromisoformat(self.state.last_mv3_prompt_at)
        except ValueError:
            return True
        return last.date() < datetime.now(timezone.utc).date()

    def resume_label(self) -> str:
        section = self._active_section()
        if self.state.session_active:
            return f"{section} — {self.state.phase.value}"
        if not self.mvp_complete():
            return f"{STAGE_SECTIONS[self.state.current_stage]} — resume"
        if self.optional_stages_remaining():
            return "Context-Specific Behavior — optional"
        return ""

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

        self.state.session_active = True
        self.state.interview_kind = InterviewKind.SEED.value
        self.state.active_questions = []
        self.state.optional_interview_active = False
        self.state.pe2_refresh_active = False
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

    def _open_stage(self, *, intro_override: str | None = None) -> SeedTurnResult:
        stage = self.state.current_stage
        section = self._active_section()
        intro = intro_override or STAGE_INTROS.get(stage, f"Let's explore {section}.")
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
        section = self._active_section()
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
        section = self._active_section()

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
        section = self._active_section()
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
        section = self._active_section()
        lowered = text.lower().strip()
        is_pe2 = self.state.interview_kind == InterviewKind.PE2_REFRESH.value

        if lowered in _APPROVE:
            self.state.phase = InterviewPhase.APPROVED
            history_source = "pe2" if is_pe2 else "seed"
            self._store_stage(section, self.state.pending_summary, source=history_source)
            self.state.phase = InterviewPhase.STORED

            if is_pe2:
                stamp = datetime.now(timezone.utc).isoformat()
                self.state.pe2_last_at[section] = stamp
                self._end_session()
                return SeedTurnResult(
                    phase=InterviewPhase.STORED,
                    stage=stage,
                    stored=True,
                    interview_complete=True,
                    messages=[
                        f"Updated **{section}** from your refresh interview. "
                        "Continue in your next session if you want to refresh another dimension."
                    ],
                )

            if stage.value not in self.state.completed_stages:
                self.state.completed_stages.append(stage.value)
            self._advance_stage()
            self._end_session()

            if self.profile_complete():
                return SeedTurnResult(
                    phase=InterviewPhase.STORED,
                    stage=stage,
                    stored=True,
                    interview_complete=True,
                    messages=[
                        f"Saved **{section}**. Personality profile complete — thank you!"
                    ],
                )

            if self.mvp_complete() and stage == InterviewStage.HUMOR:
                return SeedTurnResult(
                    phase=InterviewPhase.STORED,
                    stage=stage,
                    stored=True,
                    interview_complete=True,
                    messages=[
                        f"Saved **{section}**. MVP complete — your personality model is now active. "
                        "You can continue the optional profile interview anytime."
                    ],
                )

            return SeedTurnResult(
                phase=InterviewPhase.STORED,
                stage=stage,
                stored=True,
                interview_complete=True,
                messages=[
                    f"Saved **{section}**. Continue the next dimension in your next session — "
                    "use the banner or say 'continue personality interview'."
                ],
            )

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
        fallback = f"For **{section}**, I understood: {answer}"
        prompt = (
            f"Interview dimension: {section}\n"
            f"Question: {question}\n"
            f"User answer: {answer}\n\n"
            "Reflect back what you understood in 1-2 sentences. "
            "Do not ask a new question."
        )
        return self._complete_text(
            prompt,
            system="You are conducting a personality interview. Be concise and accurate.",
            max_tokens=200,
            temperature=0.2,
            fallback=fallback,
        )

    def _summarize_stage(self, section: str) -> str:
        answers = self.state.answers.get(section, [])
        joined = " ".join(answers)
        if not joined:
            return f"Summary for {section}."
        prompt = (
            f"Dimension: {section}\n"
            f"User answers during interview:\n{joined}\n\n"
            "Write a concise third-person summary for a personality profile wiki page. "
            "2-4 sentences. Facts only from the answers."
        )
        return self._complete_text(
            prompt,
            system="Write personality profile summaries. Return only the summary text.",
            max_tokens=300,
            temperature=0.3,
            fallback=joined,
        )

    def _complete_text(
        self,
        prompt: str,
        *,
        system: str,
        max_tokens: int,
        temperature: float,
        fallback: str,
    ) -> str:
        if self.model is None:
            return fallback
        try:
            result = self.model.complete(
                prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if result.text.strip() and not result.offline:
                return result.text.strip()
        except ModelUnavailableError:
            pass
        return fallback

    def _current_question(self) -> str | None:
        questions = self.state.active_questions or STAGE_QUESTIONS.get(
            self.state.current_stage, []
        )
        if self.state.question_index >= len(questions):
            return None
        return questions[self.state.question_index]

    def write_section(self, section: str, summary: str) -> None:
        """Replace a you.md section body (shared by seed store and overrides)."""

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

    def read_section(self, section: str) -> str:
        content = self.wiki.read("you")
        marker = f"## {section}"
        if marker not in content:
            return ""
        _, tail = content.split(marker, 1)
        body = tail.split("\n## ", 1)[0].strip()
        return body

    def _store_stage(self, section: str, summary: str, *, source: str = "seed") -> None:
        if self.living_doc is not None:
            self.living_doc.write_section_with_history(section, summary, source)
        else:
            self.write_section(section, summary)

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
                optional_interview_active=bool(data.get("optional_interview_active", False)),
                session_active=bool(data.get("session_active", False)),
                interview_kind=str(data.get("interview_kind", InterviewKind.SEED.value)),
                pe2_section=str(data.get("pe2_section", "")),
                pe2_refresh_active=bool(data.get("pe2_refresh_active", False)),
                active_questions=list(data.get("active_questions", [])),
                pe2_last_at=dict(data.get("pe2_last_at", {})),
                last_pe2_prompt_at=str(data.get("last_pe2_prompt_at", "")),
                last_mv3_prompt_at=str(data.get("last_mv3_prompt_at", "")),
                overrides=data.get("overrides", {}),
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
            "optional_interview_active": self.state.optional_interview_active,
            "session_active": self.state.session_active,
            "interview_kind": self.state.interview_kind,
            "pe2_section": self.state.pe2_section,
            "pe2_refresh_active": self.state.pe2_refresh_active,
            "active_questions": self.state.active_questions,
            "pe2_last_at": self.state.pe2_last_at,
            "last_pe2_prompt_at": self.state.last_pe2_prompt_at,
            "last_mv3_prompt_at": self.state.last_mv3_prompt_at,
            "overrides": self.state.overrides,
        }
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def seed_status(self) -> dict[str, object]:
        return {
            "mvp_complete": self.mvp_complete(),
            "profile_complete": self.profile_complete(),
            "optional_remaining": self.optional_stages_remaining(),
            "optional_interview_active": self.state.optional_interview_active,
            "session_active": self.state.session_active,
            "needs_seed_gate": self.needs_seed_gate(),
            "pe2_refresh_active": self.state.pe2_refresh_active,
            "current_stage": self.state.current_stage.value,
            "phase": self.state.phase.value,
            "resume_label": self.resume_label(),
        }
