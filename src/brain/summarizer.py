"""Session summarizer per specs/brain/session-summarizer.md."""

from __future__ import annotations

import json
from pathlib import Path

from brain.memory.raw_logs import RawLogStore
from brain.model_layer import ModelLayer
from brain.models import RawLogEntry, SessionSummary


class SessionSummarizer:
    """Topic-shift chunking and meta-summary generation."""

    FALLBACK_CHUNK_SIZE = 8

    def __init__(self, raw_logs: RawLogStore, model: ModelLayer, summaries_dir: Path) -> None:
        self.raw_logs = raw_logs
        self.model = model
        self.summaries_dir = summaries_dir
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def summarize_session(self, session_id: str | None = None) -> SessionSummary | None:
        entries = self.raw_logs.read_session(session_id)
        if not entries:
            return None

        segments = self._split_segments(entries)
        segment_summaries = [self._summarize_segment(segment) for segment in segments]
        meta = self.model.complete(
            "Create a meta-summary from these segment summaries:\n"
            + "\n".join(f"- {item}" for item in segment_summaries),
            max_tokens=256,
        ).text

        summary = SessionSummary(
            session_id=entries[0].session_id,
            segments=segment_summaries,
            meta_summary=meta,
        )
        path = self.summaries_dir / f"{summary.session_id}.json"
        path.write_text(
            json.dumps(
                {
                    "session_id": summary.session_id,
                    "segments": summary.segments,
                    "meta_summary": summary.meta_summary,
                    "created_at": summary.created_at.isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return summary

    def _split_segments(self, entries: list[RawLogEntry]) -> list[list[RawLogEntry]]:
        if len(entries) <= self.FALLBACK_CHUNK_SIZE:
            return [entries]

        segments: list[list[RawLogEntry]] = []
        current: list[RawLogEntry] = []
        last_topics: set[str] = set()

        for entry in entries:
            topics = set(entry.content.lower().split()[:5])
            if current and topics and last_topics and not topics & last_topics:
                segments.append(current)
                current = []
            current.append(entry)
            last_topics = topics

        if current:
            segments.append(current)

        if len(segments) == 1 and len(entries) > self.FALLBACK_CHUNK_SIZE:
            return [
                entries[i : i + self.FALLBACK_CHUNK_SIZE]
                for i in range(0, len(entries), self.FALLBACK_CHUNK_SIZE)
            ]
        return segments

    def _summarize_segment(self, segment: list[RawLogEntry]) -> str:
        lines = [f"{entry.sender}: {entry.content}" for entry in segment]
        completion = self.model.complete(
            "Summarize this conversation segment in 2-3 sentences:\n" + "\n".join(lines),
            max_tokens=128,
        )
        return completion.text.strip()
