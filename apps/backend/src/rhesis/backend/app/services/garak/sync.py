"""
Garak test set sync service.

This module handles syncing existing Garak-imported test sets
with the latest Garak probe versions.

Each test set corresponds to a single Garak probe class. The sync
operation updates the test set's tests to match the latest prompts
from that probe class.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Set
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
        Sync a Garak-imported test set with the latest probe.

        Each test set corresponds to a single Garak probe class.
        This operation adds new prompts, removes deleted prompts,
        and keeps unchanged prompts.

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

        # Get the probe info from attributes
        module_name = test_set.attributes.get("garak_module")
        probe_class = test_set.attributes.get("garak_probe_class")

        # Support legacy format (garak_modules array)
        if not module_name or not probe_class:
            modules = test_set.attributes.get("garak_modules", [])
            if modules:
                # Legacy: sync all modules (old behavior)
                return self._sync_legacy_test_set(test_set, modules, organization_id, user_id)
            raise ValueError(f"No Garak probe information found in test set {test_set_id}")

        old_version = test_set.attributes.get("garak_version", "unknown")
        new_version = self.probe_service.garak_version

        logger.info(
            f"Syncing test set {test_set_id} ({module_name}.{probe_class}) "
            f"from Garak {old_version} to {new_version}"
        )

        # Get the latest probe from Garak
        latest_probe = self._get_probe(module_name, probe_class)
        if not latest_probe:
            raise ValueError(
                f"Probe {module_name}.{probe_class} not found in current Garak version"
            )

        # Get current prompts in the test set
        existing_probe_ids = self._get_existing_probe_ids(test_set)

        # Build latest probe IDs
        latest_probe_ids = {
            f"{latest_probe.full_name}.{idx}" for idx in range(len(latest_probe.prompts))
        }

        # Calculate diff
        to_add = latest_probe_ids - existing_probe_ids
        to_remove = existing_probe_ids - latest_probe_ids
        unchanged = existing_probe_ids & latest_probe_ids

        # Perform sync
        added_count = self._add_new_prompts(
            test_set=test_set,
            probe=latest_probe,
            probe_ids_to_add=to_add,
            organization_id=organization_id,
            user_id=user_id,
        )

        removed_count = self._remove_old_prompts(
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

    def _get_probe(self, module_name: str, class_name: str) -> Optional[GarakProbeInfo]:
        """Get a specific probe from Garak."""
        probes = self.probe_service.extract_probes_from_module(
            module_name, probe_class_names=[class_name]
        )
        return probes[0] if probes else None

    def _sync_legacy_test_set(
        self,
        test_set: TestSet,
        modules: list,
        organization_id: str,
        user_id: str,
    ) -> SyncResult:
        """
        Sync a legacy test set that contains multiple modules.

        This supports the old format where a test set contained
        all probes from multiple modules.
        """
        old_version = test_set.attributes.get("garak_version", "unknown")
        new_version = self.probe_service.garak_version

        logger.info(f"Syncing legacy test set with modules: {modules}")

        # Get current prompts
        existing_probe_ids = self._get_existing_probe_ids(test_set)

        # Get all latest probes from all modules
        all_probes = []
        for module_name in modules:
            probes = self.probe_service.extract_probes_from_module(module_name)
            all_probes.extend(probes)

        # Build latest probe IDs
        latest_probe_ids = set()
        for probe in all_probes:
            for idx in range(len(probe.prompts)):
                latest_probe_ids.add(f"{probe.full_name}.{idx}")

        # Calculate diff
        to_add = latest_probe_ids - existing_probe_ids
        to_remove = existing_probe_ids - latest_probe_ids
        unchanged = existing_probe_ids & latest_probe_ids

        # Perform sync
        added_count = 0
        for probe in all_probes:
            added_count += self._add_new_prompts(
                test_set=test_set,
                probe=probe,
                probe_ids_to_add=to_add,
                organization_id=organization_id,
                user_id=user_id,
            )

        removed_count = self._remove_old_prompts(
            test_set=test_set,
            probe_ids_to_remove=to_remove,
        )

        # Update metadata
        now = datetime.utcnow().isoformat()
        test_set.attributes = {
            **test_set.attributes,
            "garak_version": new_version,
            "last_synced_at": now,
        }

        self.db.commit()

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

    def _add_new_prompts(
        self,
        test_set: TestSet,
        probe: GarakProbeInfo,
        probe_ids_to_add: Set[str],
        organization_id: str,
        user_id: str,
    ) -> int:
        """Add new prompts from a probe to the test set."""
        org_uuid = UUID(organization_id)
        user_uuid = UUID(user_id)
        added_count = 0

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

    def _remove_old_prompts(
        self,
        test_set: TestSet,
        probe_ids_to_remove: Set[str],
    ) -> int:
        """Remove old prompts from the test set."""
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

        # Get probe info from attributes
        module_name = test_set.attributes.get("garak_module")
        probe_class = test_set.attributes.get("garak_probe_class")
        old_version = test_set.attributes.get("garak_version", "unknown")
        new_version = self.probe_service.garak_version

        # Support legacy format
        if not module_name or not probe_class:
            modules = test_set.attributes.get("garak_modules", [])
            if modules:
                return self._get_legacy_sync_preview(test_set, modules)
            return None

        # Get the latest probe
        latest_probe = self._get_probe(module_name, probe_class)
        if not latest_probe:
            return {
                "can_sync": False,
                "old_version": old_version,
                "new_version": new_version,
                "to_add": 0,
                "to_remove": 0,
                "unchanged": 0,
                "probe_class": probe_class,
                "module_name": module_name,
                "error": f"Probe {module_name}.{probe_class} not found in current Garak",
                "last_synced_at": test_set.attributes.get("last_synced_at"),
            }

        # Get current and latest probe IDs
        existing_probe_ids = self._get_existing_probe_ids(test_set)
        latest_probe_ids = {
            f"{latest_probe.full_name}.{idx}" for idx in range(len(latest_probe.prompts))
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
            "probe_class": probe_class,
            "module_name": module_name,
            "last_synced_at": test_set.attributes.get("last_synced_at"),
        }

    def _get_legacy_sync_preview(self, test_set: TestSet, modules: list) -> Optional[dict]:
        """Get sync preview for legacy multi-module test sets."""
        old_version = test_set.attributes.get("garak_version", "unknown")
        new_version = self.probe_service.garak_version

        # Get current probe IDs
        existing_probe_ids = self._get_existing_probe_ids(test_set)

        # Get all latest probes from all modules
        latest_probe_ids = set()
        for module_name in modules:
            probes = self.probe_service.extract_probes_from_module(module_name)
            for probe in probes:
                for idx in range(len(probe.prompts)):
                    latest_probe_ids.add(f"{probe.full_name}.{idx}")

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
