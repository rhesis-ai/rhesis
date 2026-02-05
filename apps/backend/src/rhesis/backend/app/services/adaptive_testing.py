"""Service layer for adaptive testing CRUD operations.

This service handles the conversion between TestSet (database) and TestTreeData (SDK)
for performing adaptive testing operations.
"""

import urllib.parse
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.schemas import adaptive_testing as schemas
from rhesis.backend.logging import logger


class AdaptiveTestingService:
    """Service for managing adaptive testing data within a TestSet."""

    def _load_tree_data(
        self,
        db: Session,
        test_set_id: UUID,
        organization_id: str,
    ):
        """Load TestSet and convert to TestTreeData.

        Args:
            db: Database session
            test_set_id: ID of the test set
            organization_id: Organization ID for filtering

        Returns:
            Tuple of (TestSet, TestTreeData)

        Raises:
            ValueError: If test set not found
        """
        # Import here to avoid circular imports
        from rhesis.sdk.adaptive_testing import TestTree
        from rhesis.sdk.entities import Prompt, Test
        from rhesis.sdk.entities import TestSet as SDKTestSet

        # Get test set from database
        db_test_set = crud.get_test_set(
            db, test_set_id=test_set_id, organization_id=organization_id
        )
        if not db_test_set:
            raise ValueError(f"Test set {test_set_id} not found")

        # Get all tests associated with this test set using pagination
        tests = []
        skip = 0
        limit = 100  # API max limit
        while True:
            batch, total = crud.get_test_set_tests(
                db=db,
                test_set_id=db_test_set.id,
                skip=skip,
                limit=limit,
            )
            tests.extend(batch)
            if len(batch) < limit or len(tests) >= total:
                break
            skip += limit

        # Convert DB tests to SDK Test objects
        sdk_tests = []
        for db_test in tests:
            prompt_content = ""
            if db_test.prompt:
                prompt_content = db_test.prompt.content or ""

            # Get topic name from the topic relationship if available
            topic_name = ""
            if db_test.topic:
                topic_name = db_test.topic.name or ""

            sdk_test = Test(
                id=str(db_test.id),
                topic=topic_name,
                prompt=Prompt(content=prompt_content),
                metadata=db_test.test_metadata or {},
            )
            sdk_tests.append(sdk_test)

        # Create SDK TestSet and convert to TestTreeData
        sdk_test_set = SDKTestSet(
            id=str(db_test_set.id),
            name=db_test_set.name,
            tests=sdk_tests,
        )

        tree_data = TestTree.from_test_set(sdk_test_set)
        return db_test_set, tree_data

    def _save_tree_data(
        self,
        db: Session,
        db_test_set,
        tree_data,
        organization_id: str,
        user_id: str,
    ):
        """Save TestTreeData back to the database.

        This performs a full sync: updates existing tests, creates new ones,
        and removes tests that are no longer in the tree.

        Args:
            db: Database session
            db_test_set: Database TestSet model
            tree_data: TestTreeData to save
            organization_id: Organization ID
            user_id: User ID for audit
        """

        # Convert tree nodes to Test objects
        tests_to_save = []
        for order_index, node in enumerate(tree_data):
            # Decode URI-encoded topic
            topic = urllib.parse.unquote(node.topic) if node.topic else ""

            metadata = {
                "tree_id": str(node.id),
                "tree_order": order_index,
                "output": node.output,
                "label": node.label,
                "labeler": node.labeler,
                "model_score": node.model_score,
            }

            tests_to_save.append(
                {
                    "tree_id": node.id,
                    "topic": topic,
                    "input": node.input,
                    "metadata": metadata,
                    "is_topic_marker": node.label == "topic_marker",
                }
            )

        # Get all existing tests using pagination
        existing_tests = []
        skip = 0
        limit = 100  # API max limit
        while True:
            batch, total = crud.get_test_set_tests(
                db=db,
                test_set_id=db_test_set.id,
                skip=skip,
                limit=limit,
            )
            existing_tests.extend(batch)
            if len(batch) < limit or len(existing_tests) >= total:
                break
            skip += limit

        # Build map of existing tests by tree_id
        existing_by_tree_id = {}
        for test in existing_tests:
            if test.test_metadata and test.test_metadata.get("tree_id"):
                existing_by_tree_id[test.test_metadata["tree_id"]] = test

        # Track which tree_ids we've processed
        processed_tree_ids = set()

        for test_data in tests_to_save:
            tree_id = test_data["tree_id"]
            processed_tree_ids.add(tree_id)

            if tree_id in existing_by_tree_id:
                # Update existing test - pass dict directly
                db_test = existing_by_tree_id[tree_id]
                crud.update_test(
                    db=db,
                    test_id=db_test.id,
                    test={"test_metadata": test_data["metadata"]},
                    organization_id=organization_id,
                    user_id=user_id,
                )
                # Update prompt content
                if db_test.prompt and test_data["input"]:
                    crud.update_prompt(
                        db=db,
                        prompt_id=db_test.prompt.id,
                        prompt={"content": test_data["input"]},
                        organization_id=organization_id,
                        user_id=user_id,
                    )
            else:
                # Create new test
                from rhesis.backend.app.schemas.prompt import PromptCreate

                # First create the prompt
                prompt_create = PromptCreate(
                    content=test_data["input"] or "",
                    language_code="en",  # Default to English
                )
                new_prompt = crud.create_prompt(
                    db=db,
                    prompt=prompt_create,
                    organization_id=organization_id,
                    user_id=user_id,
                )

                # Create the test with a dict to avoid schema issues
                # (TestCreate schema has test_set_id which isn't a model column)
                # Note: 'topic' is a relationship, not a column - topic info is in metadata
                test_data_dict = {
                    "prompt_id": new_prompt.id,
                    "test_metadata": test_data["metadata"],
                }
                new_test = crud.create_test(
                    db=db,
                    test=test_data_dict,
                    organization_id=organization_id,
                    user_id=user_id,
                )
                # Associate with test set using the association table
                from rhesis.backend.app.models.test import test_test_set_association

                db.execute(
                    test_test_set_association.insert().values(
                        test_id=new_test.id,
                        test_set_id=db_test_set.id,
                        organization_id=UUID(organization_id),
                        user_id=UUID(user_id),
                    )
                )
                db.flush()

        # Remove tests that are no longer in tree
        for tree_id, db_test in existing_by_tree_id.items():
            if tree_id not in processed_tree_ids:
                crud.delete_test(
                    db=db,
                    test_id=db_test.id,
                    organization_id=organization_id,
                    user_id=user_id,
                )

        db.commit()

    # =========================================================================
    # Test Operations
    # =========================================================================

    def get_tests(
        self,
        db: Session,
        test_set_id: UUID,
        organization_id: str,
        topic: Optional[str] = None,
    ) -> List[schemas.TestNode]:
        """Get all tests in the test tree.

        Args:
            db: Database session
            test_set_id: ID of the test set
            organization_id: Organization ID for filtering
            topic: Optional topic to filter by

        Returns:
            List of test nodes
        """
        _, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        tests = tree_data.get_tests()
        if topic:
            # URL encode the topic for comparison
            encoded_topic = urllib.parse.quote(topic, safe="/")
            tests = [t for t in tests if t.topic == encoded_topic]

        return [
            schemas.TestNode(
                id=t.id,
                topic=t.topic,
                input=t.input,
                output=t.output,
                label=t.label if t.label in ("", "pass", "fail") else "",
                labeler=t.labeler,
                to_eval=t.to_eval,
                model_score=t.model_score,
            )
            for t in tests
        ]

    def get_test(
        self,
        db: Session,
        test_set_id: UUID,
        test_id: str,
        organization_id: str,
    ) -> Optional[schemas.TestNode]:
        """Get a specific test by ID.

        Args:
            db: Database session
            test_set_id: ID of the test set
            test_id: ID of the test node
            organization_id: Organization ID for filtering

        Returns:
            Test node or None if not found
        """
        _, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        try:
            node = tree_data[test_id]
            if node.label == "topic_marker":
                return None
            return schemas.TestNode(
                id=node.id,
                topic=node.topic,
                input=node.input,
                output=node.output,
                label=node.label if node.label in ("", "pass", "fail") else "",
                labeler=node.labeler,
                to_eval=node.to_eval,
                model_score=node.model_score,
            )
        except (KeyError, ValueError):
            return None

    def create_test(
        self,
        db: Session,
        test_set_id: UUID,
        test: schemas.TestNodeCreate,
        organization_id: str,
        user_id: str,
    ) -> schemas.TestNode:
        """Create a new test node.

        Args:
            db: Database session
            test_set_id: ID of the test set
            test: Test data to create
            organization_id: Organization ID
            user_id: User ID for audit

        Returns:
            Created test node
        """
        from rhesis.sdk.adaptive_testing.schemas import TestTreeNode

        db_test_set, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        # Create the node
        node = TestTreeNode(
            topic=test.topic,
            input=test.input,
            output=test.output,
            label=test.label,
            labeler=test.labeler or user_id,
            to_eval=test.to_eval,
            model_score=test.model_score,
        )

        # Add to tree (this also creates topic markers)
        added_node = tree_data.add_test(node)

        # Save back to database
        self._save_tree_data(db, db_test_set, tree_data, organization_id, user_id)

        return schemas.TestNode(
            id=added_node.id,
            topic=added_node.topic,
            input=added_node.input,
            output=added_node.output,
            label=added_node.label if added_node.label in ("", "pass", "fail") else "",
            labeler=added_node.labeler,
            to_eval=added_node.to_eval,
            model_score=added_node.model_score,
        )

    def update_test(
        self,
        db: Session,
        test_set_id: UUID,
        test_id: str,
        test: schemas.TestNodeUpdate,
        organization_id: str,
        user_id: str,
    ) -> Optional[schemas.TestNode]:
        """Update an existing test node.

        Args:
            db: Database session
            test_set_id: ID of the test set
            test_id: ID of the test to update
            test: Update data
            organization_id: Organization ID
            user_id: User ID for audit

        Returns:
            Updated test node or None if not found
        """
        db_test_set, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        try:
            # Build update kwargs (only include non-None values)
            update_kwargs = {}
            if test.topic is not None:
                update_kwargs["topic"] = test.topic
            if test.input is not None:
                update_kwargs["input"] = test.input
            if test.output is not None:
                update_kwargs["output"] = test.output
            if test.label is not None:
                update_kwargs["label"] = test.label
            if test.to_eval is not None:
                update_kwargs["to_eval"] = test.to_eval
            if test.model_score is not None:
                update_kwargs["model_score"] = test.model_score

            updated_node = tree_data.update_test(test_id, **update_kwargs)

            # Save back to database
            self._save_tree_data(db, db_test_set, tree_data, organization_id, user_id)

            return schemas.TestNode(
                id=updated_node.id,
                topic=updated_node.topic,
                input=updated_node.input,
                output=updated_node.output,
                label=(updated_node.label if updated_node.label in ("", "pass", "fail") else ""),
                labeler=updated_node.labeler,
                to_eval=updated_node.to_eval,
                model_score=updated_node.model_score,
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to update test {test_id}: {e}")
            return None

    def delete_test(
        self,
        db: Session,
        test_set_id: UUID,
        test_id: str,
        organization_id: str,
        user_id: str,
    ) -> bool:
        """Delete a test node.

        Args:
            db: Database session
            test_set_id: ID of the test set
            test_id: ID of the test to delete
            organization_id: Organization ID
            user_id: User ID for audit

        Returns:
            True if deleted, False if not found
        """
        db_test_set, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        try:
            deleted = tree_data.delete_test(test_id)
            if deleted:
                self._save_tree_data(db, db_test_set, tree_data, organization_id, user_id)
            return deleted
        except ValueError as e:
            logger.warning(f"Failed to delete test {test_id}: {e}")
            return False

    # =========================================================================
    # Topic Operations
    # =========================================================================

    def get_topics(
        self,
        db: Session,
        test_set_id: UUID,
        organization_id: str,
        parent: Optional[str] = None,
    ) -> List[schemas.Topic]:
        """Get all topics or children of a parent topic.

        Args:
            db: Database session
            test_set_id: ID of the test set
            organization_id: Organization ID for filtering
            parent: Optional parent path to get children of

        Returns:
            List of topics
        """
        _, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        topic_tree = tree_data.topics

        if parent is not None:
            # Get children of parent
            parent_topic = topic_tree.get(parent) if parent else None
            topics = topic_tree.get_children(parent_topic)
        else:
            # Get all topics
            topics = topic_tree.get_all()

        return [
            schemas.Topic(
                path=t.path,
                name=t.name,
                parent_path=t.parent_path,
                depth=t.depth,
                display_name=t.display_name,
                display_path=t.display_path,
                has_direct_tests=topic_tree.has_direct_tests(t),
                has_subtopics=topic_tree.has_subtopics(t),
            )
            for t in topics
        ]

    def get_topic(
        self,
        db: Session,
        test_set_id: UUID,
        topic_path: str,
        organization_id: str,
    ) -> Optional[schemas.Topic]:
        """Get a specific topic by path.

        Args:
            db: Database session
            test_set_id: ID of the test set
            topic_path: Path of the topic (URL-encoded)
            organization_id: Organization ID for filtering

        Returns:
            Topic or None if not found
        """
        _, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        topic_tree = tree_data.topics
        topic = topic_tree.get(topic_path)

        if not topic:
            return None

        return schemas.Topic(
            path=topic.path,
            name=topic.name,
            parent_path=topic.parent_path,
            depth=topic.depth,
            display_name=topic.display_name,
            display_path=topic.display_path,
            has_direct_tests=topic_tree.has_direct_tests(topic),
            has_subtopics=topic_tree.has_subtopics(topic),
        )

    def create_topic(
        self,
        db: Session,
        test_set_id: UUID,
        topic: schemas.TopicCreate,
        organization_id: str,
        user_id: str,
    ) -> schemas.Topic:
        """Create a new topic.

        Args:
            db: Database session
            test_set_id: ID of the test set
            topic: Topic data to create
            organization_id: Organization ID
            user_id: User ID for audit

        Returns:
            Created topic
        """
        db_test_set, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        topic_tree = tree_data.topics
        created_topic = topic_tree.add_topic(topic.path, labeler=topic.labeler)

        # Save back to database
        self._save_tree_data(db, db_test_set, tree_data, organization_id, user_id)

        return schemas.Topic(
            path=created_topic.path,
            name=created_topic.name,
            parent_path=created_topic.parent_path,
            depth=created_topic.depth,
            display_name=created_topic.display_name,
            display_path=created_topic.display_path,
            has_direct_tests=topic_tree.has_direct_tests(created_topic),
            has_subtopics=topic_tree.has_subtopics(created_topic),
        )

    def update_topic(
        self,
        db: Session,
        test_set_id: UUID,
        topic_path: str,
        update: schemas.TopicUpdate,
        organization_id: str,
        user_id: str,
    ) -> Optional[schemas.Topic]:
        """Update a topic (rename or move).

        Args:
            db: Database session
            test_set_id: ID of the test set
            topic_path: Path of the topic to update
            update: Update data (new_name or new_path)
            organization_id: Organization ID
            user_id: User ID for audit

        Returns:
            Updated topic or None if not found
        """
        db_test_set, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        topic_tree = tree_data.topics
        topic = topic_tree.get(topic_path)

        if not topic:
            return None

        if update.new_path is not None:
            # Move operation
            updated_topic = topic_tree.move(topic, update.new_path)
        elif update.new_name is not None:
            # Rename operation
            updated_topic = topic_tree.rename(topic, update.new_name)
        else:
            # No update specified
            return schemas.Topic(
                path=topic.path,
                name=topic.name,
                parent_path=topic.parent_path,
                depth=topic.depth,
                display_name=topic.display_name,
                display_path=topic.display_path,
                has_direct_tests=topic_tree.has_direct_tests(topic),
                has_subtopics=topic_tree.has_subtopics(topic),
            )

        # Save back to database
        self._save_tree_data(db, db_test_set, tree_data, organization_id, user_id)

        return schemas.Topic(
            path=updated_topic.path,
            name=updated_topic.name,
            parent_path=updated_topic.parent_path,
            depth=updated_topic.depth,
            display_name=updated_topic.display_name,
            display_path=updated_topic.display_path,
            has_direct_tests=topic_tree.has_direct_tests(updated_topic),
            has_subtopics=topic_tree.has_subtopics(updated_topic),
        )

    def delete_topic(
        self,
        db: Session,
        test_set_id: UUID,
        topic_path: str,
        options: schemas.TopicDelete,
        organization_id: str,
        user_id: str,
    ) -> List[str]:
        """Delete a topic.

        Args:
            db: Database session
            test_set_id: ID of the test set
            topic_path: Path of the topic to delete
            options: Deletion options
            organization_id: Organization ID
            user_id: User ID for audit

        Returns:
            List of deleted node IDs
        """
        db_test_set, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        topic_tree = tree_data.topics
        topic = topic_tree.get(topic_path)

        if not topic:
            return []

        deleted_ids = topic_tree.delete(topic, move_tests_to_parent=options.move_tests_to_parent)

        # Save back to database
        self._save_tree_data(db, db_test_set, tree_data, organization_id, user_id)

        return deleted_ids

    # =========================================================================
    # Tree Operations
    # =========================================================================

    def validate_tree(
        self,
        db: Session,
        test_set_id: UUID,
        organization_id: str,
    ) -> schemas.TreeValidation:
        """Validate the test tree structure.

        Args:
            db: Database session
            test_set_id: ID of the test set
            organization_id: Organization ID for filtering

        Returns:
            Validation results
        """
        _, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        result = tree_data.validate()
        return schemas.TreeValidation(**result)

    def get_tree_stats(
        self,
        db: Session,
        test_set_id: UUID,
        organization_id: str,
    ) -> schemas.TreeStats:
        """Get statistics about the test tree.

        Args:
            db: Database session
            test_set_id: ID of the test set
            organization_id: Organization ID for filtering

        Returns:
            Tree statistics
        """
        _, tree_data = self._load_tree_data(db, test_set_id, organization_id)

        tests = tree_data.get_tests()
        topics = tree_data.topics.get_all()

        # Count tests per topic
        tests_by_topic = {}
        for test in tests:
            topic = urllib.parse.unquote(test.topic) if test.topic else "(root)"
            tests_by_topic[topic] = tests_by_topic.get(topic, 0) + 1

        return schemas.TreeStats(
            total_tests=len(tests),
            total_topics=len(topics),
            tests_by_topic=tests_by_topic,
        )
