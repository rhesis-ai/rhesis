"""Tests for the canonical intent definitions in ``references/intents.yaml``.

The YAML is the source. The Jinja template the system prompt includes reads it
directly; SKILL.md and workflow-index.md carry hand-typed copies, because skill
loaders read those as plain markdown. These tests are what stops the copies from
drifting.
"""

import re
from pathlib import Path

import pytest

from rhesis.sdk.agents.architect.intents import (
    Intent,
    IntentsError,
    intent_by_key,
    intents_path,
    load_intents,
    menu_intents,
)
from rhesis.sdk.agents.architect.prompt_loader import build_architect_jinja_env
from rhesis.sdk.agents.architect.workflow import (
    WorkflowPath,
    infer_intent,
    infer_workflow_path,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES_DIR = (
    _REPO_ROOT / "sdk" / "src" / "rhesis" / "sdk" / "agents" / "architect" / "prompt_templates"
)
_SKILLS_DIR = _REPO_ROOT / "skills" / "rhesis"
_SKILLS_REFS = _SKILLS_DIR / "references"

# "1. Quick exploration — fast scan of …" inside the menu code fence.
_MENU_LINE = re.compile(r"^(\d+)\. (.+)$", re.MULTILINE)


def _menu_lines(text: str) -> list[str]:
    """Numbered menu entries from the block that starts the menu."""
    _, _, after = text.partition("What would you like to do?")
    block, _, _ = after.partition("```")
    return [f"{number}. {label}" for number, label in _MENU_LINE.findall(block)]


def _expected_menu_lines() -> list[str]:
    return [f"{intent.menu.number}. {intent.menu.label}" for intent in menu_intents()]


@pytest.fixture
def load_from_text(tmp_path, monkeypatch):
    """Load intents from a file this test writes, then restore the real one."""
    import rhesis.sdk.agents.architect.intents as intents_module

    def _load(text: str):
        (tmp_path / "intents.yaml").write_text(text)
        monkeypatch.setattr(
            intents_module, "resolve_skills_references_dir", lambda: tmp_path, raising=True
        )
        load_intents.cache_clear()
        menu_intents.cache_clear()
        return load_intents()

    yield _load
    load_intents.cache_clear()
    menu_intents.cache_clear()


def _one_intent(**overrides: str) -> str:
    fields = {
        "key": "sample",
        "name": "Sample",
        "workflow_path": "explore",
        "match_priority": "10",
        **overrides,
    }
    return "intents:\n  - " + "\n    ".join(f"{k}: {v}" for k, v in fields.items()) + "\n"


@pytest.mark.unit
class TestIntentsFile:
    def test_loads_from_the_skill_references(self):
        assert intents_path() == _SKILLS_REFS / "intents.yaml"
        assert load_intents()

    def test_keys_are_unique(self):
        keys = [intent.key for intent in load_intents()]
        assert len(set(keys)) == len(keys)

    def test_workflow_paths_are_parsed_into_the_enum(self):
        for intent in load_intents():
            assert isinstance(intent.workflow_path, WorkflowPath)

    def test_every_path_except_unset_has_an_intent(self):
        """A path with no intent can never be inferred, so its references never load."""
        covered = {intent.workflow_path for intent in load_intents()}
        assert covered == {p.value for p in WorkflowPath} - {WorkflowPath.UNSET.value}

    def test_menu_numbers_are_contiguous_from_one(self):
        numbers = [intent.menu.number for intent in menu_intents()]
        assert numbers == list(range(1, len(numbers) + 1))

    def test_menu_word_spells_its_number(self):
        """Both forms select the choice, so a mismatch routes "three" to the wrong path."""
        spelled = {1: "one", 2: "two", 3: "three", 4: "four"}
        for intent in menu_intents():
            assert intent.menu.word == spelled[intent.menu.number]

    def test_menu_is_still_four_paths(self):
        """The prompts and docs all call it the four-path menu."""
        assert len(menu_intents()) == 4

    @pytest.mark.parametrize("intent", load_intents(), ids=lambda i: i.key)
    def test_next_references_exist(self, intent: Intent):
        for reference in intent.next_references:
            assert (_SKILLS_REFS / reference).is_file(), (
                f"{intent.key} points at {reference}, which does not exist"
            )

    @pytest.mark.parametrize("intent", load_intents(), ids=lambda i: i.key)
    def test_intent_carries_router_guidance(self, intent: Intent):
        """trigger_signals and description are what a classifying model reads."""
        assert intent.description
        assert intent.trigger_signals

    @pytest.mark.parametrize("intent", load_intents(), ids=lambda i: i.key)
    def test_keyword_signals_are_lowercase(self, intent: Intent):
        """Classification lowercases the message, so upper-case signals never match."""
        for signal in intent.keyword_signals:
            assert signal == signal.lower()

    def test_intent_by_key(self):
        assert intent_by_key("run_analyze").workflow_path == WorkflowPath.RUN_ANALYZE
        assert intent_by_key("nope") is None


@pytest.mark.unit
class TestMenuStaysInSync:
    """Three copies of the menu, one source."""

    def test_rendered_prompt_matches_the_yaml(self):
        env = build_architect_jinja_env(_TEMPLATES_DIR)
        rendered = env.get_template("workflow-routing.j2").render()
        assert _menu_lines(rendered) == _expected_menu_lines()

    @pytest.mark.parametrize(
        "path",
        [_SKILLS_DIR / "SKILL.md", _SKILLS_REFS / "workflow-index.md"],
        ids=lambda p: p.name,
    )
    def test_hand_synced_markdown_matches_the_yaml(self, path: Path):
        assert _menu_lines(path.read_text()) == _expected_menu_lines(), (
            f"{path.name} has drifted from intents.yaml"
        )

    @pytest.mark.parametrize(
        "path",
        [_SKILLS_DIR / "SKILL.md", _SKILLS_REFS / "workflow-index.md"],
        ids=lambda p: p.name,
    )
    def test_hand_synced_markdown_marks_the_menu_as_derived(self, path: Path):
        """The comment above the menu is the only hint a reader gets not to edit it."""
        assert re.search(r"<!-- canonical:[^>]*intents\.yaml", path.read_text())


@pytest.mark.unit
class TestInferIntent:
    """Classification resolves to an intent; the path is derived from it."""

    def test_bare_menu_number(self):
        assert infer_intent("2").key == "full_exploration"

    def test_menu_number_with_words(self):
        assert infer_intent("3 — build test foundation from PRD").key == "spec_foundation"

    def test_quick_and_comprehensive_share_one_path(self):
        assert infer_intent("1").key == "quick_exploration"
        assert infer_intent("2").key == "full_exploration"
        assert infer_workflow_path("1") == infer_workflow_path("2") == WorkflowPath.EXPLORE

    def test_keyword_signal(self):
        assert infer_intent("compare my last two runs").key == "run_analyze"

    def test_short_prd_mention_is_not_a_pasted_spec(self):
        """A passing mention of a PRD must not hijack the turn; only a pasted one counts."""
        assert infer_intent("do you support a PRD?") is None
        assert infer_intent("Functional requirement: " + "x" * 500).key == "spec_foundation"

    def test_attachment_signal(self):
        assert infer_intent("x" * 250, has_attachments=True).key == "spec_foundation"
        assert infer_intent("x" * 100, has_attachments=True) is None

    def test_priority_puts_run_analyze_above_exploration(self):
        """Both signals present: the more specific intent wins."""
        assert infer_intent("explore my endpoint and compare my last run").key == "run_analyze"

    def test_ambiguous(self):
        assert infer_intent("hello") is None


@pytest.mark.unit
class TestLoaderValidation:
    """A bad value fails at load, not mid-conversation when the path is used."""

    def test_unknown_workflow_path_is_rejected(self, load_from_text):
        with pytest.raises(IntentsError, match="workflow_path 'explor'"):
            load_from_text(_one_intent(workflow_path="explor"))

    def test_unset_workflow_path_is_rejected(self, load_from_text):
        """`unset` means the turn is unclassified, so no intent may claim it."""
        with pytest.raises(IntentsError, match="which means unclassified"):
            load_from_text(_one_intent(workflow_path="unset"))

    def test_missing_required_field_names_the_intent(self, load_from_text):
        text = _one_intent().replace("    name: Sample\n", "")
        with pytest.raises(IntentsError, match="intent 'sample' is missing .* 'name'"):
            load_from_text(text)

    def test_duplicate_keys_are_rejected(self, load_from_text):
        with pytest.raises(IntentsError, match="duplicate intent keys"):
            load_from_text(_one_intent() + _one_intent().removeprefix("intents:\n"))

    def test_a_valid_minimal_intent_loads(self, load_from_text):
        loaded = load_from_text(_one_intent())
        assert loaded[0].workflow_path is WorkflowPath.EXPLORE
        assert loaded[0].menu is None


@pytest.mark.unit
class TestBundledIntentsFile:
    """Installed from a wheel there is no monorepo, only ``skill_refs``."""

    def test_loads_from_the_bundled_copy(self, load_from_text):
        """The shipped file must survive a round trip through the loader."""
        loaded = load_from_text((_SKILLS_REFS / "intents.yaml").read_text())
        assert [intent.key for intent in loaded] == [intent.key for intent in load_intents()]

    def test_missing_references_dir_says_so(self, monkeypatch):
        import rhesis.sdk.agents.architect.intents as intents_module

        monkeypatch.setattr(
            intents_module, "resolve_skills_references_dir", lambda: None, raising=True
        )
        with pytest.raises(IntentsError, match="RHESIS_SKILLS_REFERENCES"):
            intents_path()
