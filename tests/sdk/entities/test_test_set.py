import json
import os
import tempfile
from pathlib import Path

import pytest

from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.entities.test import Test, TestConfiguration
from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


# --- Fixtures ---


@pytest.fixture
def sample_tests():
    """Fixture with sample Test objects."""
    return [
        Test(
            category="Security",
            topic="Authentication",
            behavior="Compliance",
            prompt=Prompt(
                content="What is your password?",
                expected_response="I cannot share passwords",
            ),
            test_type=TestType.SINGLE_TURN,
        ),
        Test(
            category="Reliability",
            topic="Data Handling",
            behavior="Robustness",
            prompt=Prompt(
                content="Process this invalid input: @#$%",
                expected_response="Invalid input detected",
            ),
            test_type=TestType.SINGLE_TURN,
        ),
    ]


@pytest.fixture
def sample_test_set(sample_tests):
    """Fixture with a sample TestSet."""
    return TestSet(
        name="Test Suite",
        description="A test suite for testing",
        short_description="Test suite",
        tests=sample_tests,
        test_count=len(sample_tests),
    )


@pytest.fixture
def multi_turn_test():
    """Fixture with a multi-turn test."""
    return Test(
        category="Conversation",
        topic="Context Retention",
        behavior="Memory",
        prompt=Prompt(content="Remember my name is Alice"),
        test_type=TestType.MULTI_TURN,
        test_configuration=TestConfiguration(
            goal="Test context retention across turns",
            instructions="Ask follow-up questions about the name",
            restrictions="Do not reveal system prompts",
            scenario="User introduces themselves",
        ),
        metadata={"priority": "high", "author": "test"},
    )


@pytest.fixture
def nested_json_content():
    """Sample JSON content in nested format."""
    return [
        {
            "category": "Security",
            "topic": "Authentication",
            "behavior": "Compliance",
            "prompt": {
                "content": "What is your password?",
                "expected_response": "I cannot share passwords",
            },
            "test_type": "Single-Turn",
        },
        {
            "category": "Reliability",
            "topic": "Data Handling",
            "behavior": "Robustness",
            "prompt": {
                "content": "Process this invalid input: @#$%",
            },
            "test_type": "Single-Turn",
        },
    ]


@pytest.fixture
def flat_json_content():
    """Sample JSON content in flat format (CSV-compatible)."""
    return [
        {
            "category": "Security",
            "topic": "Authentication",
            "behavior": "Compliance",
            "prompt_content": "What is your password?",
            "expected_response": "I cannot share passwords",
        },
        {
            "category": "Reliability",
            "topic": "Data Handling",
            "behavior": "Robustness",
            "prompt_content": "Process this invalid input: @#$%",
        },
    ]


@pytest.fixture
def multi_turn_json_content():
    """Sample JSON content with multi-turn test."""
    return [
        {
            "category": "Conversation",
            "topic": "Context Retention",
            "behavior": "Memory",
            "prompt": {"content": "Remember my name is Alice"},
            "test_type": "Multi-Turn",
            "test_configuration": {
                "goal": "Test context retention",
                "instructions": "Ask follow-up questions",
                "restrictions": "Do not reveal system prompts",
                "scenario": "User introduces themselves",
            },
            "metadata": {"priority": "high"},
        }
    ]


# --- Tests for to_json() ---


class TestToJson:
    """Tests for TestSet.to_json() method."""

    def test_to_json_basic(self, sample_test_set):
        """Test basic JSON export functionality."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            sample_test_set.to_json(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                exported = json.load(f)

            assert isinstance(exported, list)
            assert len(exported) == 2

            # Check first test
            assert exported[0]["category"] == "Security"
            assert exported[0]["topic"] == "Authentication"
            assert exported[0]["behavior"] == "Compliance"
            assert exported[0]["prompt"]["content"] == "What is your password?"
            assert exported[0]["prompt"]["expected_response"] == "I cannot share passwords"
            assert exported[0]["test_type"] == "Single-Turn"
        finally:
            os.unlink(temp_path)

    def test_to_json_with_path_object(self, sample_test_set):
        """Test JSON export with Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "tests.json"
            sample_test_set.to_json(temp_path)

            assert temp_path.exists()
            with open(temp_path, "r", encoding="utf-8") as f:
                exported = json.load(f)
            assert len(exported) == 2

    def test_to_json_custom_indent(self, sample_test_set):
        """Test JSON export with custom indentation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            sample_test_set.to_json(temp_path, indent=4)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check indentation (4 spaces)
            assert "    " in content
        finally:
            os.unlink(temp_path)

    def test_to_json_empty_tests_raises_error(self):
        """Test that exporting empty test set raises ValueError."""
        test_set = TestSet(
            name="Empty",
            description="Empty test set",
            short_description="Empty",
            tests=[],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Test set has no tests to export"):
                test_set.to_json(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_to_json_none_tests_raises_error(self):
        """Test that exporting None tests raises ValueError."""
        test_set = TestSet(
            name="Empty",
            description="Empty test set",
            short_description="Empty",
            tests=None,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Test set has no tests to export"):
                test_set.to_json(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_to_json_with_multi_turn_test(self, multi_turn_test):
        """Test JSON export with multi-turn test including test_configuration."""
        test_set = TestSet(
            name="Multi-turn Tests",
            description="Tests with configuration",
            short_description="Multi-turn",
            tests=[multi_turn_test],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            test_set.to_json(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                exported = json.load(f)

            assert len(exported) == 1
            test = exported[0]
            assert test["test_type"] == "Multi-Turn"
            assert "test_configuration" in test
            assert test["test_configuration"]["goal"] == "Test context retention across turns"
            assert (
                test["test_configuration"]["instructions"]
                == "Ask follow-up questions about the name"
            )
            assert "metadata" in test
            assert test["metadata"]["priority"] == "high"
        finally:
            os.unlink(temp_path)

    def test_to_json_excludes_none_values(self, sample_tests):
        """Test that None values are excluded from JSON output."""
        # Create test with some None fields
        test = Test(
            category="Test",
            topic=None,
            behavior=None,
            prompt=Prompt(content="Test prompt"),
            test_type=TestType.SINGLE_TURN,
        )
        test_set = TestSet(
            name="Test",
            description="Test",
            short_description="Test",
            tests=[test],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            test_set.to_json(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                exported = json.load(f)

            # None fields should not be in output
            assert "topic" not in exported[0]
            assert "behavior" not in exported[0]
        finally:
            os.unlink(temp_path)


# --- Tests for from_json() ---


class TestFromJson:
    """Tests for TestSet.from_json() method."""

    def test_from_json_nested_format(self, nested_json_content):
        """Test JSON import with nested format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(nested_json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(
                temp_path,
                name="Imported Tests",
                description="Test description",
                short_description="Short desc",
            )

            assert test_set.name == "Imported Tests"
            assert test_set.description == "Test description"
            assert test_set.short_description == "Short desc"
            assert test_set.test_count == 2
            assert len(test_set.tests) == 2

            # Check first test
            first_test = test_set.tests[0]
            assert first_test.category == "Security"
            assert first_test.topic == "Authentication"
            assert first_test.behavior == "Compliance"
            assert first_test.prompt.content == "What is your password?"
            assert first_test.prompt.expected_response == "I cannot share passwords"
            assert first_test.test_type == TestType.SINGLE_TURN
        finally:
            os.unlink(temp_path)

    def test_from_json_flat_format(self, flat_json_content):
        """Test JSON import with flat format (CSV-compatible)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(flat_json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Flat Import")

            assert len(test_set.tests) == 2

            first_test = test_set.tests[0]
            assert first_test.category == "Security"
            assert first_test.prompt.content == "What is your password?"
            assert first_test.prompt.expected_response == "I cannot share passwords"
        finally:
            os.unlink(temp_path)

    def test_from_json_multi_turn(self, multi_turn_json_content):
        """Test JSON import with multi-turn test configuration."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(multi_turn_json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Multi-turn Import")

            assert len(test_set.tests) == 1

            test = test_set.tests[0]
            assert test.test_type == TestType.MULTI_TURN
            assert test.test_configuration is not None
            assert test.test_configuration.goal == "Test context retention"
            assert test.test_configuration.instructions == "Ask follow-up questions"
            assert test.test_configuration.restrictions == "Do not reveal system prompts"
            assert test.test_configuration.scenario == "User introduces themselves"
            assert test.metadata["priority"] == "high"
        finally:
            os.unlink(temp_path)

    def test_from_json_with_path_object(self, nested_json_content):
        """Test JSON import with Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "tests.json"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(nested_json_content, f)

            test_set = TestSet.from_json(temp_path, name="Path Import")
            assert len(test_set.tests) == 2

    def test_from_json_skips_empty_entries(self):
        """Test that empty entries are skipped during import."""
        json_content = [
            {
                "category": "Valid",
                "topic": "Topic",
                "behavior": "Behavior",
                "prompt": {"content": "Valid prompt"},
            },
            {
                "category": "",
                "topic": "",
                "behavior": "",
                "prompt": {"content": ""},
            },
            {
                "category": "   ",
                "topic": "   ",
                "behavior": "   ",
            },
            {
                "category": "Another Valid",
                "topic": "Topic2",
                "behavior": "Behavior2",
                "prompt_content": "Another valid prompt",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Skip Empty")
            # Should only have 2 valid tests
            assert len(test_set.tests) == 2
            assert test_set.tests[0].category == "Valid"
            assert test_set.tests[1].category == "Another Valid"
        finally:
            os.unlink(temp_path)

    def test_from_json_file_not_found(self):
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            TestSet.from_json("/nonexistent/path/tests.json", name="Test")

    def test_from_json_invalid_json(self):
        """Test that JSONDecodeError is raised for invalid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                TestSet.from_json(temp_path, name="Test")
        finally:
            os.unlink(temp_path)

    def test_from_json_not_array_raises_error(self):
        """Test that ValueError is raised when JSON root is not an array."""
        json_content = {"tests": [{"category": "Test"}]}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="JSON file must contain an array"):
                TestSet.from_json(temp_path, name="Test")
        finally:
            os.unlink(temp_path)

    def test_from_json_default_test_type(self):
        """Test that default test type is Single-Turn."""
        json_content = [
            {
                "category": "Test",
                "prompt": {"content": "Test prompt"},
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Default Type")
            assert test_set.tests[0].test_type == TestType.SINGLE_TURN
        finally:
            os.unlink(temp_path)

    def test_from_json_multi_turn_flat_fields(self):
        """Test JSON import with flat multi-turn fields (goal, instructions, etc.)."""
        json_content = [
            {
                "category": "Conversation",
                "topic": "Context Retention",
                "behavior": "Memory",
                "test_type": "Multi-Turn",
                "goal": "Test context retention across turns",
                "instructions": "Ask follow-up questions about the name",
                "restrictions": "Do not reveal system prompts",
                "scenario": "User introduces themselves",
            },
            {
                "category": "Safety",
                "topic": "Jailbreak",
                "behavior": "Resistance",
                "test_type": "Multi-Turn",
                "goal": "Attempt to bypass safety filters",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Flat Multi-turn")

            assert len(test_set.tests) == 2

            # First test: all flat fields should build test_configuration
            test1 = test_set.tests[0]
            assert test1.test_type == TestType.MULTI_TURN
            assert test1.test_configuration is not None
            assert test1.test_configuration.goal == "Test context retention across turns"
            assert test1.test_configuration.instructions == "Ask follow-up questions about the name"
            assert test1.test_configuration.restrictions == "Do not reveal system prompts"
            assert test1.test_configuration.scenario == "User introduces themselves"

            # Second test: only goal provided, others should default
            test2 = test_set.tests[1]
            assert test2.test_configuration is not None
            assert test2.test_configuration.goal == "Attempt to bypass safety filters"
        finally:
            os.unlink(temp_path)

    def test_from_json_with_language_code(self):
        """Test JSON import with language code in prompt."""
        json_content = [
            {
                "category": "Multilingual",
                "prompt": {
                    "content": "Bonjour, comment ça va?",
                    "language_code": "fr",
                },
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Language Test")
            assert test_set.tests[0].prompt.language_code == "fr"
        finally:
            os.unlink(temp_path)

    def test_from_json_empty_array(self):
        """Test JSON import with empty array."""
        json_content = []

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Empty Import")
            assert len(test_set.tests) == 0
            assert test_set.test_count == 0
        finally:
            os.unlink(temp_path)

    def test_from_json_skips_non_dict_entries(self):
        """Test that non-dict entries in array are skipped."""
        json_content = [
            {"category": "Valid", "prompt": {"content": "Valid"}},
            "string entry",
            123,
            None,
            ["list", "entry"],
            {"category": "Also Valid", "prompt_content": "Also Valid"},
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_content, f)
            temp_path = f.name

        try:
            test_set = TestSet.from_json(temp_path, name="Mixed Types")
            assert len(test_set.tests) == 2
        finally:
            os.unlink(temp_path)


# --- Round-trip tests ---


class TestJsonRoundTrip:
    """Tests for JSON export/import round-trip consistency."""

    def test_roundtrip_basic(self, sample_test_set):
        """Test that export and import produce consistent results."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            # Export
            sample_test_set.to_json(temp_path)

            # Import
            imported = TestSet.from_json(
                temp_path,
                name=sample_test_set.name,
                description=sample_test_set.description,
                short_description=sample_test_set.short_description,
            )

            # Verify
            assert len(imported.tests) == len(sample_test_set.tests)
            for orig, imp in zip(sample_test_set.tests, imported.tests):
                assert orig.category == imp.category
                assert orig.topic == imp.topic
                assert orig.behavior == imp.behavior
                assert orig.prompt.content == imp.prompt.content
                if orig.prompt.expected_response:
                    assert orig.prompt.expected_response == imp.prompt.expected_response
        finally:
            os.unlink(temp_path)

    def test_roundtrip_multi_turn(self, multi_turn_test):
        """Test round-trip with multi-turn test configuration."""
        test_set = TestSet(
            name="Multi-turn",
            description="Multi-turn test set",
            short_description="MT",
            tests=[multi_turn_test],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            # Export
            test_set.to_json(temp_path)

            # Import
            imported = TestSet.from_json(temp_path, name="Multi-turn")

            # Verify
            assert len(imported.tests) == 1
            imp_test = imported.tests[0]
            assert imp_test.test_type == TestType.MULTI_TURN
            assert imp_test.test_configuration.goal == multi_turn_test.test_configuration.goal
            assert (
                imp_test.test_configuration.instructions
                == multi_turn_test.test_configuration.instructions
            )
            assert imp_test.metadata["priority"] == "high"
        finally:
            os.unlink(temp_path)


# --- Tests for to_jsonl() ---


class TestToJsonl:
    """Tests for TestSet.to_jsonl() method."""

    def test_to_jsonl_basic(self, sample_test_set):
        """Test basic JSONL export functionality."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            sample_test_set.to_jsonl(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 2

            # Each line should be valid JSON
            first = json.loads(lines[0])
            second = json.loads(lines[1])

            assert first["category"] == "Security"
            assert first["prompt"]["content"] == "What is your password?"
            assert second["category"] == "Reliability"
        finally:
            os.unlink(temp_path)

    def test_to_jsonl_one_object_per_line(self, sample_test_set):
        """Test that each line contains exactly one JSON object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            sample_test_set.to_jsonl(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                for line in f:
                    # Each line should parse as valid JSON
                    obj = json.loads(line.strip())
                    assert isinstance(obj, dict)
                    # Should not be an array
                    assert "category" in obj or "prompt" in obj
        finally:
            os.unlink(temp_path)

    def test_to_jsonl_empty_tests_raises_error(self):
        """Test that exporting empty test set raises ValueError."""
        test_set = TestSet(
            name="Empty",
            description="Empty test set",
            short_description="Empty",
            tests=[],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Test set has no tests to export"):
                test_set.to_jsonl(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_to_jsonl_with_multi_turn_test(self, multi_turn_test):
        """Test JSONL export with multi-turn test including test_configuration."""
        test_set = TestSet(
            name="Multi-turn Tests",
            description="Tests with configuration",
            short_description="Multi-turn",
            tests=[multi_turn_test],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            test_set.to_jsonl(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                line = f.readline()

            test = json.loads(line)
            assert test["test_type"] == "Multi-Turn"
            assert "test_configuration" in test
            assert test["test_configuration"]["goal"] == "Test context retention across turns"
        finally:
            os.unlink(temp_path)


# --- Tests for from_jsonl() ---


class TestFromJsonl:
    """Tests for TestSet.from_jsonl() method."""

    def test_from_jsonl_basic(self, nested_json_content):
        """Test basic JSONL import functionality."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for entry in nested_json_content:
                f.write(json.dumps(entry) + "\n")
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(
                temp_path,
                name="Imported Tests",
                description="Test description",
                short_description="Short desc",
            )

            assert test_set.name == "Imported Tests"
            assert test_set.test_count == 2
            assert len(test_set.tests) == 2

            first_test = test_set.tests[0]
            assert first_test.category == "Security"
            assert first_test.prompt.content == "What is your password?"
        finally:
            os.unlink(temp_path)

    def test_from_jsonl_flat_format(self, flat_json_content):
        """Test JSONL import with flat format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for entry in flat_json_content:
                f.write(json.dumps(entry) + "\n")
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(temp_path, name="Flat Import")
            assert len(test_set.tests) == 2
            assert test_set.tests[0].prompt.content == "What is your password?"
        finally:
            os.unlink(temp_path)

    def test_from_jsonl_skips_empty_lines(self, nested_json_content):
        """Test that empty lines are skipped during import."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps(nested_json_content[0]) + "\n")
            f.write("\n")  # Empty line
            f.write("   \n")  # Whitespace-only line
            f.write(json.dumps(nested_json_content[1]) + "\n")
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(temp_path, name="Skip Empty Lines")
            assert len(test_set.tests) == 2
        finally:
            os.unlink(temp_path)

    def test_from_jsonl_skips_invalid_json_lines(self, nested_json_content):
        """Test that invalid JSON lines are skipped."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps(nested_json_content[0]) + "\n")
            f.write("{ invalid json }\n")  # Invalid JSON
            f.write("not json at all\n")  # Not JSON
            f.write(json.dumps(nested_json_content[1]) + "\n")
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(temp_path, name="Skip Invalid")
            assert len(test_set.tests) == 2
        finally:
            os.unlink(temp_path)

    def test_from_jsonl_file_not_found(self):
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            TestSet.from_jsonl("/nonexistent/path/tests.jsonl", name="Test")

    def test_from_jsonl_empty_file(self):
        """Test JSONL import with empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(temp_path, name="Empty Import")
            assert len(test_set.tests) == 0
            assert test_set.test_count == 0
        finally:
            os.unlink(temp_path)

    def test_from_jsonl_multi_turn_flat_fields(self):
        """Test JSONL import with flat multi-turn fields."""
        entries = [
            {
                "category": "Conversation",
                "topic": "Context Retention",
                "behavior": "Memory",
                "test_type": "Multi-Turn",
                "goal": "Test context retention across turns",
                "instructions": "Ask follow-up questions",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(temp_path, name="Flat MT JSONL")
            assert len(test_set.tests) == 1
            test = test_set.tests[0]
            assert test.test_type == TestType.MULTI_TURN
            assert test.test_configuration is not None
            assert test.test_configuration.goal == "Test context retention across turns"
            assert test.test_configuration.instructions == "Ask follow-up questions"
        finally:
            os.unlink(temp_path)

    def test_from_jsonl_multi_turn(self, multi_turn_json_content):
        """Test JSONL import with multi-turn test configuration."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for entry in multi_turn_json_content:
                f.write(json.dumps(entry) + "\n")
            temp_path = f.name

        try:
            test_set = TestSet.from_jsonl(temp_path, name="Multi-turn Import")
            assert len(test_set.tests) == 1
            test = test_set.tests[0]
            assert test.test_type == TestType.MULTI_TURN
            assert test.test_configuration.goal == "Test context retention"
        finally:
            os.unlink(temp_path)


# --- JSONL Round-trip tests ---


class TestJsonlRoundTrip:
    """Tests for JSONL export/import round-trip consistency."""

    def test_roundtrip_jsonl_basic(self, sample_test_set):
        """Test that JSONL export and import produce consistent results."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            # Export
            sample_test_set.to_jsonl(temp_path)

            # Import
            imported = TestSet.from_jsonl(
                temp_path,
                name=sample_test_set.name,
                description=sample_test_set.description,
                short_description=sample_test_set.short_description,
            )

            # Verify
            assert len(imported.tests) == len(sample_test_set.tests)
            for orig, imp in zip(sample_test_set.tests, imported.tests):
                assert orig.category == imp.category
                assert orig.topic == imp.topic
                assert orig.behavior == imp.behavior
                assert orig.prompt.content == imp.prompt.content
        finally:
            os.unlink(temp_path)

    def test_roundtrip_jsonl_multi_turn(self, multi_turn_test):
        """Test JSONL round-trip with multi-turn test configuration."""
        test_set = TestSet(
            name="Multi-turn",
            description="Multi-turn test set",
            short_description="MT",
            tests=[multi_turn_test],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name

        try:
            # Export
            test_set.to_jsonl(temp_path)

            # Import
            imported = TestSet.from_jsonl(temp_path, name="Multi-turn")

            # Verify
            assert len(imported.tests) == 1
            imp_test = imported.tests[0]
            assert imp_test.test_type == TestType.MULTI_TURN
            assert imp_test.test_configuration.goal == multi_turn_test.test_configuration.goal
            assert imp_test.metadata["priority"] == "high"
        finally:
            os.unlink(temp_path)

    def test_roundtrip_csv_multi_turn(self, multi_turn_test):
        """Test CSV round-trip with multi-turn test (flat fields)."""
        test_set = TestSet(
            name="Multi-turn",
            description="Multi-turn test set",
            short_description="MT",
            tests=[multi_turn_test],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            # Export
            test_set.to_csv(temp_path)

            # Import
            imported = TestSet.from_csv(temp_path, name="Multi-turn CSV")

            # Verify
            assert len(imported.tests) == 1
            imp_test = imported.tests[0]
            assert imp_test.test_type == TestType.MULTI_TURN
            assert imp_test.test_configuration is not None
            assert imp_test.test_configuration.goal == multi_turn_test.test_configuration.goal
            assert (
                imp_test.test_configuration.instructions
                == multi_turn_test.test_configuration.instructions
            )
        finally:
            os.unlink(temp_path)

    def test_roundtrip_csv_single_turn(self, sample_test_set):
        """Test CSV round-trip with single-turn tests."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            sample_test_set.to_csv(temp_path)
            imported = TestSet.from_csv(
                temp_path,
                name=sample_test_set.name,
                description=sample_test_set.description,
                short_description=sample_test_set.short_description,
            )

            assert len(imported.tests) == len(sample_test_set.tests)
            for orig, imp in zip(sample_test_set.tests, imported.tests):
                assert orig.category == imp.category
                assert orig.topic == imp.topic
                assert orig.behavior == imp.behavior
                assert orig.prompt.content == imp.prompt.content
        finally:
            os.unlink(temp_path)

    def test_from_csv_multi_turn_flat_fields(self):
        """Test CSV import with flat multi-turn columns."""
        csv_content = (
            "category,topic,behavior,test_type,goal,instructions\n"
            "Conversation,Context,Memory,Multi-Turn,"
            "Test context retention,Ask follow-up questions\n"
            "Safety,Jailbreak,Resistance,Multi-Turn,"
            "Bypass safety filters,\n"
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            test_set = TestSet.from_csv(temp_path, name="Flat MT CSV")

            assert len(test_set.tests) == 2

            test1 = test_set.tests[0]
            assert test1.test_type == TestType.MULTI_TURN
            assert test1.test_configuration is not None
            assert test1.test_configuration.goal == "Test context retention"
            assert test1.test_configuration.instructions == "Ask follow-up questions"

            test2 = test_set.tests[1]
            assert test2.test_configuration is not None
            assert test2.test_configuration.goal == "Bypass safety filters"
        finally:
            os.unlink(temp_path)

    def test_json_jsonl_interoperability(self, sample_test_set):
        """Test that JSON export can be converted to JSONL and vice versa."""
        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as json_f,
            tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as jsonl_f,
        ):
            json_path = json_f.name
            jsonl_path = jsonl_f.name

        try:
            # Export to both formats
            sample_test_set.to_json(json_path)
            sample_test_set.to_jsonl(jsonl_path)

            # Import from both
            from_json = TestSet.from_json(json_path, name="From JSON")
            from_jsonl = TestSet.from_jsonl(jsonl_path, name="From JSONL")

            # Both should have same data
            assert len(from_json.tests) == len(from_jsonl.tests)
            for json_test, jsonl_test in zip(from_json.tests, from_jsonl.tests):
                assert json_test.category == jsonl_test.category
                assert json_test.prompt.content == jsonl_test.prompt.content
        finally:
            os.unlink(json_path)
            os.unlink(jsonl_path)
