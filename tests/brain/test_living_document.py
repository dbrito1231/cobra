"""Tests for living document updates."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.config import BrainConfig
from brain.living_document import LivingDocumentManager
from brain.memory.wiki import WikiStore
from brain.model_layer import ModelLayer
from brain.seed_document import MVP_STAGES, SeedDocumentManager


@pytest.fixture
def brain_dirs(tmp_path: Path) -> dict[str, Path]:
    wiki = tmp_path / "wiki"
    memory = tmp_path / "memory"
    for path in (wiki, memory):
        path.mkdir()
    return {"wiki_dir": wiki, "memory_dir": memory}


class TestLivingDocument:
    def test_session_update_appends_observed_pattern(self, brain_dirs: dict[str, Path]) -> None:
        wiki = WikiStore(brain_dirs["wiki_dir"])
        seed = SeedDocumentManager(wiki, brain_dirs["memory_dir"] / "seed_state.json")
        living = LivingDocumentManager(seed, None, brain_dirs["wiki_dir"])

        touched = living.update_from_session("User prefers concise bullet answers in the morning.")
        assert "Observed Patterns" in touched
        you = wiki.read("you")
        assert "Session note" in you or "concise" in you.lower()

    def test_override_is_authoritative(self, brain_dirs: dict[str, Path]) -> None:
        wiki = WikiStore(brain_dirs["wiki_dir"])
        seed = SeedDocumentManager(wiki, brain_dirs["memory_dir"] / "seed_state.json")
        seed.state.completed_stages = [stage.value for stage in MVP_STAGES]
        seed.write_section("Communication Style", "Direct and brief.")
        living = LivingDocumentManager(seed, None, brain_dirs["wiki_dir"])

        living.apply_override("Communication Style", "Always formal in work contexts.")
        assert "Always formal" in wiki.read("you")
        assert "Communication Style" in seed.state.overrides

        before = seed.read_section("Communication Style")
        living.update_from_session("User speaks casually in all settings.")
        after = seed.read_section("Communication Style")
        assert before == after
        assert "Always formal" in after

    def test_version_history_written(self, brain_dirs: dict[str, Path]) -> None:
        wiki = WikiStore(brain_dirs["wiki_dir"])
        seed = SeedDocumentManager(wiki, brain_dirs["memory_dir"] / "seed_state.json")
        config = BrainConfig.from_config_dict(
            {"storage": {"wiki_dir": str(brain_dirs["wiki_dir"])}}
        )
        config.offline_mode = True
        living = LivingDocumentManager(seed, ModelLayer(config), brain_dirs["wiki_dir"])
        seed.write_section("Communication Style", "Direct.")

        living.apply_override("Communication Style", "Warm and conversational.")
        history = living.read_history()
        assert "You Page Version History" in history
        assert "override" in history
