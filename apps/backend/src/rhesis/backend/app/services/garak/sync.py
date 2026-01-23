"""
Garak test set sync service.

This module handles syncing existing Garak-imported test sets
with the latest Garak probe versions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test, test_test_set_association
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.logging.rhesis_logger import logger

from .probes import GarakProbeInfo, GarakProbeService


@dataclass
class SyncResult:
    """Result of a sync operation."""

    added: int
    removed: int
    unchanged: int
    new_garak_version: str
    old_garak_version: str


class GarakSyncService:
    """Service for syncing Garak-imported test sets."""

    def __init__(self, db: Session):
        self.db = db
        self.probe_service = GarakProbeService()

    def sync_test_set(
        self,
        test_set_id: str,
        organization_id: str,
        user_id: str,
    ) -> SyncResult:
        """
        Sync a Garak-imported test set with the latest probes.

        Args:
            test_set_id: ID of the test set to sync
            organization_id: Organization ID
            user_id: User ID

        Returns:
            SyncResult with counts of added/removed/unchanged tests

        Raises:
            ValueError: If test set not found or not a Garak-imported test set
        """
        test_set_uuid = UUID(test_set_id)
        org_uuid = UUID(organization_id)
        user_uuid = UUID(user_id)

        # Get the test set
        test_set = (
            self.db.query(TestSet)
            .filter(
                TestSet.id == test_set_uuid,
                TestSet.organization_id == org_uuid,
            )
            .first()
        )

        if not test_set:
            raise ValueError(f"Test set not found: {test_set_id}")

        # Verify it's a Garak-imported test set
        if not test_set.attributes or test_set.attributes.get("source") != "garak":
            raise ValueError(f"Test set {test_set_id} is not a Garak-imported test set")

        # Get the modules that were originally imported
        modules = test_set.attributes.get("garak_modules", [])
        if not modules:
            raise ValueError(f"No Garak modules found in test set {test_set_id}")

        old_version = test_set.attributes.get("garak_version", "unknown")
        new_version = self.probe_service.garak_version

        logger.info(f"Syncing test set {test_set_id} from Garak {old_version} to {new_version}")

        # Get current prompts in the test set
        existing_probe_ids = self._get_existing_probe_ids(test_set)

        # Get latest probes from Garak
        latest_probes = self._get_latest_probes(modules)
        latest_probe_ids = {
            f"{p.full_name}.{idx}" for p in latest_probes for idx in range(len(p.prompts))
        }

        # Calculate diff
        to_add = latest_probe_ids - existing_probe_ids
        to_remove = existing_probe_ids - latest_probe_ids
        unchanged = existing_probe_ids & latest_probe_ids

        # Perform sync
        added_count = self._add_new_probes(
            test_set=test_set,
            probes=latest_probes,
            probe_ids_to_add=to_add,
            organization_id=organization_id,
            user_id=user_id,
        )

        removed_count = self._remove_old_probes(
            test_set=test_set,
            probe_ids_to_remove=to_remove,
        )

        # Update test set metadata
        now = datetime.utcnow().isoformat()
        test_set.attributes = {
            **test_set.attributes,
            "garak_version": new_version,
            "last_synced_at": now,
        }

        self.db.commit()

        logger.info(
            f"Sync completed: added={added_count}, removed={removed_count}, "
            f"unchanged={len(unchanged)}"
        )

        return SyncResult(
            added=added_count,
            removed=removed_count,
            unchanged=len(unchanged),
            new_garak_version=new_version,
            old_garak_version=old_version,
        )

    def _get_existing_probe_ids(self, test_set: TestSet) -> Set[str]:
        """Get the set of Garak probe IDs currently in the test set."""
        probe_ids = set()

        for test in test_set.tests:
            if test.test_metadata and test.test_metadata.get("source") == "garak":
                probe_id = test.test_metadata.get("garak_probe_id")
                if probe_id:
                    probe_ids.add(probe_id)

        return probe_ids

    def _get_latest_probes(self, modules: List[str]) -> List[GarakProbeInfo]:
        """Get the latest probes from specified modules."""
        all_probes = []

        for module_name in modules:
            probes = self.probe_service.extract_probes_from_module(module_name)
            all_probes.extend(probes)

        return all_probes

    def _add_new_probes(
        self,
        test_set: TestSet,
        probes: List[GarakProbeInfo],
        probe_ids_to_add: Set[str],
        organization_id: str,
        user_id: str,
    ) -> int:
        """Add new probes to the test set."""
        org_uuid = UUID(organization_id)
        user_uuid = UUID(user_id)
        added_count = 0

        for probe in probes:
            for idx, prompt_content in enumerate(probe.prompts):
                probe_id = f"{probe.full_name}.{idx}"
                if probe_id not in probe_ids_to_add:
                    continue

                if not prompt_content or not prompt_content.strip():
                    continue

                # Create test metadata
                test_metadata = {
                    "source": "garak",
                    "garak_probe_id": probe_id,
                    "garak_probe_class": probe.class_name,
                    "garak_module": probe.module_name,
                    "garak_tags": probe.tags,
                }

                # Create prompt
                from rhesis.backend.app.models.prompt import Prompt

                prompt = Prompt(
                    id=uuid4(),
                    content=prompt_content,
                    organization_id=org_uuid,
                    user_id=user_uuid,
                )
                self.db.add(prompt)
                self.db.flush()

                # Create test
                test = Test(
                    id=uuid4(),
                    prompt_id=prompt.id,
                    organization_id=org_uuid,
                    user_id=user_uuid,
                    test_metadata=test_metadata,
                )
                self.db.add(test)
                self.db.flush()

                # Associate with test set
                self.db.execute(
                    test_test_set_association.insert().values(
                        test_id=test.id,
                        test_set_id=test_set.id,
                        organization_id=org_uuid,
                        user_id=user_uuid,
                    )
                )

                added_count += 1

        return added_count

    def _remove_old_probes(
        self,
        test_set: TestSet,
        probe_ids_to_remove: Set[str],
    ) -> int:
        """Remove old probes from the test set."""
        removed_count = 0

        for test in list(test_set.tests):  # Create list copy to allow modification
            if not test.test_metadata or test.test_metadata.get("source") != "garak":
                continue

            probe_id = test.test_metadata.get("garak_probe_id")
            if probe_id and probe_id in probe_ids_to_remove:
                # Remove test-testset association
                self.db.execute(
                    test_test_set_association.delete().where(
                        test_test_set_association.c.test_id == test.id,
                        test_test_set_association.c.test_set_id == test_set.id,
                    )
                )

                # Optionally delete the test itself if not associated with other test sets
                # For now, we just remove the association
                removed_count += 1

        return removed_count

    def can_sync(self, test_set_id: str, organization_id: str) -> bool:
        """
        Check if a test set can be synced.

        Args:
            test_set_id: ID of the test set
            organization_id: Organization ID

        Returns:
            True if the test set is a Garak-imported test set
        """
        test_set = (
            self.db.query(TestSet)
            .filter(
                TestSet.id == UUID(test_set_id),
                TestSet.organization_id == UUID(organization_id),
            )
            .first()
        )

        if not test_set:
            return False

        return test_set.attributes is not None and test_set.attributes.get("source") == "garak"

    def get_sync_preview(
        self,
        test_set_id: str,
        organization_id: str,
    ) -> Optional[dict]:
        """
        Get a preview of what would change during sync.

        Args:
            test_set_id: ID of the test set
            organization_id: Organization ID

        Returns:
            Dictionary with preview information or None if not syncable
        """
        test_set_uuid = UUID(test_set_id)
        org_uuid = UUID(organization_id)

        test_set = (
            self.db.query(TestSet)
            .filter(
                TestSet.id == test_set_uuid,
                TestSet.organization_id == org_uuid,
            )
            .first()
        )

        if not test_set or not test_set.attributes:
            return None

        if test_set.attributes.get("source") != "garak":
            return None

        modules = test_set.attributes.get("garak_modules", [])
        old_version = test_set.attributes.get("garak_version", "unknown")
        new_version = self.probe_service.garak_version

        # Get current and latest probe IDs
        existing_probe_ids = self._get_existing_probe_ids(test_set)
        latest_probes = self._get_latest_probes(modules)
        latest_probe_ids = {
            f"{p.full_name}.{idx}" for p in latest_probes for idx in range(len(p.prompts))
        }

        to_add = latest_probe_ids - existing_probe_ids
        to_remove = existing_probe_ids - latest_probe_ids
        unchanged = existing_probe_ids & latest_probe_ids

        return {
            "can_sync": True,
            "old_version": old_version,
            "new_version": new_version,
            "to_add": len(to_add),
            "to_remove": len(to_remove),
            "unchanged": len(unchanged),
            "modules": modules,
            "last_synced_at": test_set.attributes.get("last_synced_at"),
        }
