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
- create_explorer_test: the prompt+test insert pair, with and without a prompt
- update_explorer_test: selective field application, and the topic reload it depends on
- reassign_tests_topic: per-test topic moves, including orphaning
- remove_tests_from_test_set: batched association detach
- replace_test_set_adaptive_settings / set_test_set_default_endpoint: replace vs patch
- set_explorer_test_metadata: batched metadata writes

Run with: python -m pytest tests/backend/crud/test_explorer_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.explorer import (
    create_explorer_test,
    find_unused_test_set_name,
    get_test_in_test_set,
    get_tests_under_topic,
    reassign_tests_topic,
    remove_tests_from_test_set,
    replace_test_set_adaptive_settings,
    set_explorer_test_metadata,
    set_test_set_default_endpoint,
    update_explorer_test,
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


@pytest.mark.unit
@pytest.mark.crud
class TestCreateExplorerTest:
    """➕ The prompt+test insert pair"""

    def test_creates_the_prompt_and_the_test(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        topic = _create_topic(
            test_db, f"Insert {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )

        db_test = create_explorer_test(
            test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_id=topic.id,
            content="What is the capital of France?",
            metadata={"output": "Paris", "label": "pass", "labeler": "user", "model_score": 1.0},
        )

        assert db_test.id is not None
        assert db_test.prompt_id is not None
        assert db_test.prompt.content == "What is the capital of France?"
        assert db_test.topic_id == topic.id
        assert db_test.test_metadata["label"] == "pass"

    def test_no_content_means_no_prompt_row(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """This is how topic markers are stored -- a test with no prompt."""
        topic = _create_topic(
            test_db, f"Marker {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )

        db_test = create_explorer_test(
            test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            topic_id=topic.id,
            metadata={"label": "topic_marker", "labeler": "user", "output": ""},
        )

        assert db_test.id is not None
        assert db_test.prompt_id is None
        assert db_test.prompt is None

    def test_an_empty_string_still_creates_a_prompt(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Only None skips the prompt; "" is a prompt with no text."""
        db_test = create_explorer_test(
            test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            content="",
        )

        assert db_test.prompt_id is not None
        assert db_test.prompt.content == ""


@pytest.mark.unit
@pytest.mark.crud
class TestUpdateExplorerTest:
    """✏️ Selective test updates"""

    @pytest.fixture
    def existing_test(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        marker = uuid.uuid4().hex[:8]
        test_set = _create_test_set(test_db, f"Update {marker}", test_org_id, authenticated_user_id)
        topic = _create_topic(test_db, f"Before {marker}", test_org_id, authenticated_user_id)
        db_test = _create_test(
            test_db,
            test_set,
            test_org_id,
            authenticated_user_id,
            topic=topic,
            prompt_content="original input",
            metadata={"output": "old", "label": "", "labeler": "user", "model_score": 0.0},
        )
        return test_set, db_test, marker

    def test_updates_prompt_metadata_and_topic_together(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, existing_test
    ):
        _, db_test, marker = existing_test
        new_topic = _create_topic(test_db, f"After {marker}", test_org_id, authenticated_user_id)

        updated = update_explorer_test(
            test_db,
            db_test,
            prompt_content="new input",
            metadata={"output": "new", "label": "pass", "labeler": "model", "model_score": 0.9},
            topic_id=new_topic.id,
        )

        assert updated.prompt.content == "new input"
        assert updated.test_metadata["label"] == "pass"
        assert updated.topic_id == new_topic.id

    def test_the_topic_relationship_reflects_the_new_id(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, existing_test
    ):
        """Assigning topic_id does not update .topic -- the refresh inside is why it does."""
        _, db_test, marker = existing_test
        new_topic = _create_topic(test_db, f"Reloaded {marker}", test_org_id, authenticated_user_id)

        updated = update_explorer_test(test_db, db_test, topic_id=new_topic.id)

        assert updated.topic.name == f"Reloaded {marker}"

    def test_none_arguments_leave_their_fields_alone(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str, existing_test
    ):
        _, db_test, _ = existing_test
        original_topic_id = db_test.topic_id

        updated = update_explorer_test(test_db, db_test, metadata={"output": "only this"})

        assert updated.prompt.content == "original input"
        assert updated.topic_id == original_topic_id
        assert updated.test_metadata == {"output": "only this"}

    def test_a_test_without_a_prompt_ignores_prompt_content(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Topic markers have no prompt row to write into."""
        test_set = _create_test_set(
            test_db, f"NoPrompt {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        marker = _create_test(
            test_db,
            test_set,
            test_org_id,
            authenticated_user_id,
            metadata={"label": "topic_marker"},
        )

        updated = update_explorer_test(test_db, marker, prompt_content="ignored")

        assert updated.prompt is None


@pytest.mark.unit
@pytest.mark.crud
class TestReassignTestsTopic:
    """🔀 Moving tests between topics"""

    def test_each_test_moves_to_its_own_paired_topic(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Renaming a subtree gives every test a different rewritten path."""
        marker = uuid.uuid4().hex[:8]
        test_set = _create_test_set(test_db, f"Rename {marker}", test_org_id, authenticated_user_id)
        old = _create_topic(test_db, f"Old {marker}", test_org_id, authenticated_user_id)
        t1 = _create_test(
            test_db, test_set, test_org_id, authenticated_user_id, topic=old, prompt_content="a"
        )
        t2 = _create_test(
            test_db, test_set, test_org_id, authenticated_user_id, topic=old, prompt_content="b"
        )
        new_a = _create_topic(test_db, f"New {marker}/A", test_org_id, authenticated_user_id)
        new_b = _create_topic(test_db, f"New {marker}/B", test_org_id, authenticated_user_id)

        reassign_tests_topic(test_db, [(t1, new_a), (t2, new_b)])

        assert t1.topic_id == new_a.id
        assert t2.topic_id == new_b.id

    def test_a_none_topic_orphans_the_test(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Removing a top-level topic leaves its tests with no topic at all."""
        marker = uuid.uuid4().hex[:8]
        test_set = _create_test_set(test_db, f"Orphan {marker}", test_org_id, authenticated_user_id)
        topic = _create_topic(test_db, f"Doomed {marker}", test_org_id, authenticated_user_id)
        db_test = _create_test(
            test_db, test_set, test_org_id, authenticated_user_id, topic=topic, prompt_content="x"
        )

        reassign_tests_topic(test_db, [(db_test, None)])

        assert db_test.topic_id is None
        assert db_test.topic is None

    def test_an_empty_batch_is_a_no_op(self, test_db: Session):
        reassign_tests_topic(test_db, [])


@pytest.mark.unit
@pytest.mark.crud
class TestRemoveTestsFromTestSet:
    """✂️ Detaching tests from a set"""

    def test_detaches_the_whole_batch_in_one_go(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        marker = uuid.uuid4().hex[:8]
        test_set = _create_test_set(test_db, f"Detach {marker}", test_org_id, authenticated_user_id)
        tests = [
            _create_test(
                test_db,
                test_set,
                test_org_id,
                authenticated_user_id,
                prompt_content=f"prompt {i}",
            )
            for i in range(3)
        ]

        remove_tests_from_test_set(test_db, test_set.id, [t.id for t in tests[:2]])

        remaining = test_db.execute(
            test_test_set_association.select().where(
                test_test_set_association.c.test_set_id == test_set.id
            )
        ).fetchall()
        assert [row.test_id for row in remaining] == [tests[2].id]

    def test_only_the_named_test_set_is_touched(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """The same test can belong to two sets; detaching from one must not affect the other."""
        marker = uuid.uuid4().hex[:8]
        set_a = _create_test_set(test_db, f"A {marker}", test_org_id, authenticated_user_id)
        set_b = _create_test_set(test_db, f"B {marker}", test_org_id, authenticated_user_id)
        db_test = _create_test(
            test_db, set_a, test_org_id, authenticated_user_id, prompt_content="shared"
        )
        test_db.execute(
            test_test_set_association.insert().values(
                test_id=db_test.id,
                test_set_id=set_b.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.flush()

        remove_tests_from_test_set(test_db, set_a.id, [db_test.id])

        still_in_b = test_db.execute(
            test_test_set_association.select().where(
                test_test_set_association.c.test_set_id == set_b.id,
                test_test_set_association.c.test_id == db_test.id,
            )
        ).fetchall()
        assert len(still_in_b) == 1

    def test_an_empty_batch_is_a_no_op(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = _create_test_set(
            test_db, f"Empty {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        db_test = _create_test(
            test_db, test_set, test_org_id, authenticated_user_id, prompt_content="kept"
        )

        remove_tests_from_test_set(test_db, test_set.id, [])

        rows = test_db.execute(
            test_test_set_association.select().where(
                test_test_set_association.c.test_set_id == test_set.id
            )
        ).fetchall()
        assert [row.test_id for row in rows] == [db_test.id]


@pytest.mark.unit
@pytest.mark.crud
class TestAdaptiveSettingsWrites:
    """⚙️ Replace vs patch on adaptive_settings"""

    def test_replace_overwrites_the_whole_block(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = _create_test_set(
            test_db, f"Replace {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        test_set.attributes = {
            "metadata": {"behaviors": ["Adaptive Testing"]},
            "adaptive_settings": {"default_endpoint_id": "stale", "other": "dropped"},
        }
        test_db.flush()

        replace_test_set_adaptive_settings(test_db, test_set, {"default_endpoint_id": "fresh"})

        assert test_set.attributes["adaptive_settings"] == {"default_endpoint_id": "fresh"}
        # Everything outside adaptive_settings survives.
        assert test_set.attributes["metadata"] == {"behaviors": ["Adaptive Testing"]}

    def test_patching_the_endpoint_keeps_the_other_settings(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = _create_test_set(
            test_db, f"Patch {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        test_set.attributes = {"adaptive_settings": {"kept": "yes", "default_endpoint_id": "old"}}
        test_db.flush()
        endpoint_id = uuid.uuid4()

        set_test_set_default_endpoint(test_db, test_set, endpoint_id)

        assert test_set.attributes["adaptive_settings"]["default_endpoint_id"] == str(endpoint_id)
        assert test_set.attributes["adaptive_settings"]["kept"] == "yes"

    def test_patching_a_set_with_no_settings_yet(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = _create_test_set(
            test_db, f"Fresh {uuid.uuid4().hex[:8]}", test_org_id, authenticated_user_id
        )
        endpoint_id = uuid.uuid4()

        set_test_set_default_endpoint(test_db, test_set, endpoint_id)

        assert test_set.attributes["adaptive_settings"] == {"default_endpoint_id": str(endpoint_id)}


@pytest.mark.unit
@pytest.mark.crud
class TestSetExplorerTestMetadata:
    """📝 Batched metadata writes"""

    def test_writes_each_test_its_own_metadata(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        marker = uuid.uuid4().hex[:8]
        test_set = _create_test_set(
            test_db, f"Verdict {marker}", test_org_id, authenticated_user_id
        )
        t1 = _create_test(
            test_db,
            test_set,
            test_org_id,
            authenticated_user_id,
            prompt_content="a",
            metadata={"output": "a-out", "label": ""},
        )
        t2 = _create_test(
            test_db,
            test_set,
            test_org_id,
            authenticated_user_id,
            prompt_content="b",
            metadata={"output": "b-out", "label": ""},
        )

        set_explorer_test_metadata(
            test_db,
            [
                (t1, {"output": "a-out", "label": "pass", "model_score": 0.9}),
                (t2, {"output": "b-out", "label": "fail", "model_score": 0.1}),
            ],
        )

        test_db.refresh(t1)
        test_db.refresh(t2)
        assert t1.test_metadata["label"] == "pass"
        assert t2.test_metadata["label"] == "fail"

    def test_an_empty_batch_is_a_no_op(self, test_db: Session):
        set_explorer_test_metadata(test_db, [])
