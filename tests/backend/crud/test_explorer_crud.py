"""
🧭 Explorer CRUD Operations Testing

Covers the query behaviour that the Explorer services used to hand-roll and that
``crud/explorer.py`` now owns. The consolidations and the one-query name search are
the parts worth pinning: the services no longer see the SQL, so a regression here
would surface as odd tree or import behaviour rather than as a query error.

Functions tested:
- find_unused_test_set_name: collision-free naming without a query per candidate
- get_test_in_test_set: membership-scoped single-test lookup
- get_tests_under_topic: topic subtree matching

Run with: python -m pytest tests/backend/crud/test_explorer_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.explorer import (
    find_unused_test_set_name,
    get_test_in_test_set,
    get_tests_under_topic,
)
from rhesis.backend.app.models.test import test_test_set_association


def _create_test_set(db: Session, name: str, organization_id: str, user_id: str) -> models.TestSet:
    test_set = models.TestSet(name=name, organization_id=organization_id, user_id=user_id)
    db.add(test_set)
    db.flush()
    return test_set


def _create_topic(db: Session, name: str, organization_id: str, user_id: str) -> models.Topic:
    topic = models.Topic(name=name, organization_id=organization_id, user_id=user_id)
    db.add(topic)
    db.flush()
    return topic


def _create_test(
    db: Session,
    test_set: models.TestSet,
    organization_id: str,
    user_id: str,
    topic: models.Topic | None = None,
    prompt_content: str | None = None,
    metadata: dict | None = None,
) -> models.Test:
    prompt = None
    if prompt_content is not None:
        prompt = models.Prompt(
            content=prompt_content, organization_id=organization_id, user_id=user_id
        )
        db.add(prompt)
        db.flush()

    test = models.Test(
        topic_id=topic.id if topic else None,
        prompt_id=prompt.id if prompt else None,
        test_metadata=metadata,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(test)
    db.flush()

    db.execute(
        test_test_set_association.insert().values(
            test_id=test.id,
            test_set_id=test_set.id,
            organization_id=organization_id,
            user_id=user_id,
        )
    )
    db.flush()
    return test


@pytest.mark.unit
@pytest.mark.crud
class TestFindUnusedTestSetName:
    """🏷️ Explorer import naming"""

    def test_returns_base_name_when_free(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        base = f"Naming Free {uuid.uuid4().hex[:8]}"

        assert find_unused_test_set_name(test_db, test_org_id, base) == base

    def test_counts_up_through_consecutive_collisions(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """The suffix sequence is base, base (1), base (2), ... with no gaps."""
        base = f"Naming Seq {uuid.uuid4().hex[:8]}"

        _create_test_set(test_db, base, test_org_id, authenticated_user_id)
        assert find_unused_test_set_name(test_db, test_org_id, base) == f"{base} (1)"

        _create_test_set(test_db, f"{base} (1)", test_org_id, authenticated_user_id)
        assert find_unused_test_set_name(test_db, test_org_id, base) == f"{base} (2)"

        _create_test_set(test_db, f"{base} (2)", test_org_id, authenticated_user_id)
        assert find_unused_test_set_name(test_db, test_org_id, base) == f"{base} (3)"

    def test_fills_a_gap_in_the_sequence(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """(2) taken but (1) free still yields (1) -- matches the old probe loop."""
        base = f"Naming Gap {uuid.uuid4().hex[:8]}"
        _create_test_set(test_db, base, test_org_id, authenticated_user_id)
        _create_test_set(test_db, f"{base} (2)", test_org_id, authenticated_user_id)

        assert find_unused_test_set_name(test_db, test_org_id, base) == f"{base} (1)"

    def test_like_wildcards_in_the_base_name_do_not_widen_the_match(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """A '%' or '_' in the name is data, not a pattern."""
        marker = uuid.uuid4().hex[:8]
        base = f"100% Coverage {marker}"
        _create_test_set(test_db, f"1009 Coverage {marker} (1)", test_org_id, authenticated_user_id)

        # The decoy would only collide if '%' were treated as a wildcard.
        assert find_unused_test_set_name(test_db, test_org_id, base) == base

        _create_test_set(test_db, base, test_org_id, authenticated_user_id)
        assert find_unused_test_set_name(test_db, test_org_id, base) == f"{base} (1)"

    def test_a_name_taken_in_another_organization_does_not_collide(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Names are unique per organization, so another tenant's row must not shadow it."""
        base = f"Naming Tenant {uuid.uuid4().hex[:8]}"
        _create_test_set(test_db, base, test_org_id, authenticated_user_id)

        assert find_unused_test_set_name(test_db, str(uuid.uuid4()), base) == base


@pytest.mark.unit
@pytest.mark.crud
class TestGetTestInTestSet:
    """🔎 Membership-scoped test lookup"""

    def test_returns_the_test_with_its_prompt_loaded(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = _create_test_set(
            test_db, f"Lookup {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        test = _create_test(
            test_db,
            test_set,
            test_org_id,
            authenticated_user_id,
            prompt_content="How do I do the thing?",
        )

        found = get_test_in_test_set(test_db, test_set.id, test.id, test_org_id)

        assert found is not None
        assert found.id == test.id
        assert found.prompt.content == "How do I do the thing?"

    def test_returns_none_for_a_test_in_a_different_set(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """The membership join is the authorization check -- it must not be optional."""
        marker = uuid.uuid4().hex[:8]
        owning_set = _create_test_set(
            test_db, f"Owner {marker}", test_org_id, authenticated_user_id
        )
        other_set = _create_test_set(test_db, f"Other {marker}", test_org_id, authenticated_user_id)
        test = _create_test(
            test_db, owning_set, test_org_id, authenticated_user_id, prompt_content="Owned"
        )

        assert get_test_in_test_set(test_db, other_set.id, test.id, test_org_id) is None

    def test_returns_none_for_another_organization(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = _create_test_set(
            test_db, f"Tenant {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        test = _create_test(
            test_db, test_set, test_org_id, authenticated_user_id, prompt_content="Mine"
        )

        assert get_test_in_test_set(test_db, test_set.id, test.id, str(uuid.uuid4())) is None

    def test_returns_a_test_without_a_prompt(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Topic markers carry no prompt; the eager load must tolerate that."""
        test_set = _create_test_set(
            test_db, f"Marker {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        marker = _create_test(
            test_db,
            test_set,
            test_org_id,
            authenticated_user_id,
            metadata={"label": "topic_marker"},
        )

        found = get_test_in_test_set(test_db, test_set.id, marker.id, test_org_id)

        assert found is not None
        assert found.prompt is None


@pytest.mark.unit
@pytest.mark.crud
class TestGetTestsUnderTopic:
    """🌳 Topic subtree matching"""

    @pytest.fixture
    def topic_tree(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """A set with Safety, Safety/Violence, Safety/Violence/Weapons and Safetyville."""
        marker = uuid.uuid4().hex[:8]
        test_set = _create_test_set(test_db, f"Tree {marker}", test_org_id, authenticated_user_id)

        tests = {}
        for path in (
            f"Safety {marker}",
            f"Safety {marker}/Violence",
            f"Safety {marker}/Violence/Weapons",
            f"Safety {marker}ville",
        ):
            topic = _create_topic(test_db, path, test_org_id, authenticated_user_id)
            tests[path] = _create_test(
                test_db,
                test_set,
                test_org_id,
                authenticated_user_id,
                topic=topic,
                prompt_content=f"Prompt for {path}",
            )

        return test_set, tests, marker

    def test_includes_the_topic_and_all_descendants(
        self, test_db: Session, test_org_id, topic_tree
    ):
        test_set, tests, marker = topic_tree

        found = get_tests_under_topic(test_db, test_set.id, test_org_id, f"Safety {marker}")

        assert {t.id for t in found} == {
            tests[f"Safety {marker}"].id,
            tests[f"Safety {marker}/Violence"].id,
            tests[f"Safety {marker}/Violence/Weapons"].id,
        }

    def test_a_sibling_sharing_the_name_prefix_is_excluded(
        self, test_db: Session, test_org_id, topic_tree
    ):
        """'Safetyville' is not under 'Safety' -- the separator matters."""
        test_set, tests, marker = topic_tree

        found = get_tests_under_topic(test_db, test_set.id, test_org_id, f"Safety {marker}")

        assert tests[f"Safety {marker}ville"].id not in {t.id for t in found}

    def test_a_subtopic_returns_only_its_own_branch(
        self, test_db: Session, test_org_id, topic_tree
    ):
        test_set, tests, marker = topic_tree

        found = get_tests_under_topic(
            test_db, test_set.id, test_org_id, f"Safety {marker}/Violence"
        )

        assert {t.id for t in found} == {
            tests[f"Safety {marker}/Violence"].id,
            tests[f"Safety {marker}/Violence/Weapons"].id,
        }

    def test_the_topic_is_eager_loaded(self, test_db: Session, test_org_id, topic_tree):
        """Callers read test.topic.name to rewrite paths, so it must come back loaded."""
        test_set, _, marker = topic_tree

        found = get_tests_under_topic(test_db, test_set.id, test_org_id, f"Safety {marker}")

        assert all(t.topic is not None for t in found)
        assert {t.topic.name for t in found} == {
            f"Safety {marker}",
            f"Safety {marker}/Violence",
            f"Safety {marker}/Violence/Weapons",
        }

    def test_tests_in_another_set_are_excluded(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, topic_tree
    ):
        test_set, tests, marker = topic_tree
        other_set = _create_test_set(
            test_db, f"Other tree {marker}", test_org_id, authenticated_user_id
        )
        topic = _create_topic(
            test_db, f"Safety {marker}/Elsewhere", test_org_id, authenticated_user_id
        )
        stranger = _create_test(
            test_db,
            other_set,
            test_org_id,
            authenticated_user_id,
            topic=topic,
            prompt_content="Not in the tree under test",
        )

        found = get_tests_under_topic(test_db, test_set.id, test_org_id, f"Safety {marker}")

        assert stranger.id not in {t.id for t in found}

    def test_unknown_topic_returns_empty(self, test_db: Session, test_org_id, topic_tree):
        test_set, _, marker = topic_tree

        assert get_tests_under_topic(test_db, test_set.id, test_org_id, f"Nope {marker}") == []
