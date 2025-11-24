import pytest
from requests import HTTPError

from rhesis.sdk.entities.behavior import Behavior
from rhesis.sdk.entities.category import Category
from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.entities.topic import Topic

# ============================================================================
# Behavior Tests
# ============================================================================


def test_behavior(db_cleanup):
    behavior = Behavior(
        name="Test Behavior",
        description="Test Description",
    )

    result = behavior.push()

    assert result["id"] is not None
    assert result["name"] == "Test Behavior"
    assert result["description"] == "Test Description"


def test_behavior_push_pull(db_cleanup):
    behavior = Behavior(
        name="Test push pull behavior",
        description="Test push pull behavior description",
    )
    behavior.push()

    pulled_behavior = behavior.pull()

    assert pulled_behavior.name == "Test push pull behavior"
    assert pulled_behavior.description == "Test push pull behavior description"


def test_behavior_delete(db_cleanup):
    behavior = Behavior(
        name="Test push pull behavior",
        description="Test push pull behavior description",
    )

    behavior.push()
    behavior.delete()

    with pytest.raises(HTTPError):
        behavior.pull()


# ============================================================================
# Category Tests
# ============================================================================


def test_category(db_cleanup):
    category = Category(
        name="Test Category",
        description="Test Category Description",
    )

    result = category.push()

    assert result["id"] is not None
    assert result["name"] == "Test Category"
    assert result["description"] == "Test Category Description"


def test_category_push_pull(db_cleanup):
    category = Category(
        name="Test push pull category",
        description="Test push pull category description",
    )
    category.push()

    pulled_category = category.pull()

    assert pulled_category.name == "Test push pull category"
    assert pulled_category.description == "Test push pull category description"


def test_category_delete(db_cleanup):
    category = Category(
        name="Test category to delete",
        description="Test category to delete description",
    )

    category.push()
    category.delete()

    with pytest.raises(HTTPError):
        category.pull()


# ============================================================================
# Topic Tests
# ============================================================================


def test_topic(db_cleanup):
    topic = Topic(
        name="Test Topic",
        description="Test Topic Description",
    )

    result = topic.push()

    assert result["id"] is not None
    assert result["name"] == "Test Topic"
    assert result["description"] == "Test Topic Description"


def test_topic_push_pull(db_cleanup):
    topic = Topic(
        name="Test push pull topic",
        description="Test push pull topic description",
    )
    topic.push()

    pulled_topic = topic.pull()

    assert pulled_topic.name == "Test push pull topic"
    assert pulled_topic.description == "Test push pull topic description"


def test_topic_delete(db_cleanup):
    topic = Topic(
        name="Test topic to delete",
        description="Test topic to delete description",
    )

    topic.push()
    topic.delete()

    with pytest.raises(HTTPError):
        topic.pull()


# ============================================================================
# Prompt Tests
# ============================================================================


def test_prompt(db_cleanup):
    prompt = Prompt(
        content="Test prompt content",
        language_code="en",
    )

    result = prompt.push()

    assert result["id"] is not None
    assert result["content"] == "Test prompt content"
    assert result["language_code"] == "en"


def test_prompt_push_pull(db_cleanup):
    prompt = Prompt(
        content="Test push pull prompt content",
        language_code="en",
    )
    prompt.push()

    pulled_prompt = prompt.pull()

    assert pulled_prompt.content == "Test push pull prompt content"
    assert pulled_prompt.language_code == "en"


def test_prompt_delete(db_cleanup):
    prompt = Prompt(
        content="Test prompt to delete",
        language_code="en",
    )

    prompt.push()
    prompt.delete()

    with pytest.raises(HTTPError):
        prompt.pull()


# ============================================================================
# TestSet Tests
# ============================================================================


def test_test_set(db_cleanup):
    test_set = TestSet(
        name="Test Test Set",
        description="Test Test Set Description",
        short_description="Test Short Description",
    )

    result = test_set.push()

    assert result["id"] is not None
    assert result["name"] == "Test Test Set"
    assert result["description"] == "Test Test Set Description"
    assert result["short_description"] == "Test Short Description"


def test_test_set_push_pull(db_cleanup):
    test_set = TestSet(
        name="Test push pull test set",
        description="Test push pull test set description",
        short_description="Test push pull short description",
    )
    test_set.push()

    pulled_test_set = test_set.pull()

    assert pulled_test_set.name == "Test push pull test set"
    assert pulled_test_set.description == "Test push pull test set description"
    assert pulled_test_set.short_description == "Test push pull short description"


def test_test_set_delete(db_cleanup):
    test_set = TestSet(
        name="Test test set to delete",
        description="Test test set to delete description",
        short_description="Test short description",
    )

    test_set.push()
    test_set.delete()

    with pytest.raises(HTTPError):
        test_set.pull()
