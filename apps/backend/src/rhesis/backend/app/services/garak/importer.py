"""
Garak probe importer service.

This module handles the import of Garak probes as Rhesis test sets,
including metric creation and association.

Uses the bulk creation infrastructure to ensure proper metadata is set
(test_set_type, test_type, status, license_type, etc.).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric
from rhesis.backend.app.models.test_set import TestSet, test_set_metric_association
from rhesis.backend.app.schemas import test_set as test_set_schemas
from rhesis.backend.app.services.test_set import bulk_create_test_set
from rhesis.backend.logging.rhesis_logger import logger

from .probes import GarakProbeInfo, GarakProbeService
from .taxonomy import GarakTaxonomy


@dataclass
class ProbeSelection:
    """Probe selection for import."""

    module_name: str
    class_name: str
    custom_name: Optional[str] = None


class GarakImporter:
    """Service for importing Garak probes as Rhesis test sets."""

    # Garak detector metric class name for SDK
    GARAK_METRIC_CLASS_NAME = "GarakDetectorMetric"
    GARAK_METRIC_BACKEND = "garak"

    def __init__(self, db: Session):
        self.db = db
        self.probe_service = GarakProbeService()
        self._garak_version = self.probe_service.garak_version

    def import_probes(
        self,
        probes: List[Any],  # List of GarakProbeSelection from schema
        name_prefix: Optional[str],
        description_template: Optional[str],
        organization_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Import selected Garak probes, creating one test set per probe.

        Uses the bulk creation infrastructure to ensure proper metadata is set
        (test_set_type=Single-Turn, test_type, status, license_type, etc.).

        Args:
            probes: List of probe selections (module_name, class_name, custom_name)
            name_prefix: Prefix for auto-generated test set names
            description_template: Optional description template
            organization_id: Organization ID
            user_id: User ID

        Returns:
            Dictionary with import results
        """
        logger.info(f"Importing {len(probes)} Garak probes as test sets")

        results = []
        total_tests = 0

        for probe_selection in probes:
            # Extract probe info
            probe_info = self._get_probe_info(
                probe_selection.module_name, probe_selection.class_name
            )

            if not probe_info:
                logger.warning(
                    f"Probe {probe_selection.module_name}.{probe_selection.class_name} not found"
                )
                continue

            # Generate test set name
            test_set_name = probe_selection.custom_name or self._generate_test_set_name(
                probe_info, name_prefix
            )

            # Generate description
            description = self._generate_description(probe_info, description_template)

            # Get taxonomy mapping for this probe module
            mapping = GarakTaxonomy.get_mapping(probe_info.module_name)

            # Build Garak-specific metadata for the test set
            garak_metadata = self._build_garak_metadata(probe_info)

            # Build test data for bulk creation
            tests_data = self._build_tests_data(probe_info, mapping)

            if not tests_data:
                logger.warning(f"No valid prompts found for probe {probe_info.full_name}")
                continue

            # Build test set data for bulk creation
            test_set_data = test_set_schemas.TestSetBulkCreate(
                name=test_set_name,
                description=description,
                short_description=f"Garak probe: {probe_info.full_name}",
                test_set_type="Single-Turn",  # Garak probes are single-turn
                metadata=garak_metadata,
                tests=tests_data,
            )

            # Use bulk creation infrastructure
            test_set = bulk_create_test_set(
                db=self.db,
                test_set_data=test_set_data,
                organization_id=organization_id,
                user_id=user_id,
            )

            # Store Garak attributes directly in the test set
            # (bulk_create_test_set generates standard attributes, we need to merge)
            test_set.attributes = {
                **(test_set.attributes or {}),
                **garak_metadata,
            }

            # Associate metric with test set
            detector = probe_info.detector or mapping.default_detector
            if detector:
                metric = self._get_or_create_garak_metric(
                    detector_class=detector,
                    organization_id=organization_id,
                    user_id=user_id,
                )
                self._associate_metric_with_test_set(test_set, metric, organization_id, user_id)

            test_count = len(tests_data)
            results.append(
                {
                    "test_set_id": test_set.id,
                    "test_set_name": test_set.name,
                    "probe_full_name": probe_info.full_name,
                    "test_count": test_count,
                }
            )
            total_tests += test_count

        self.db.commit()

        logger.info(f"Created {len(results)} test sets with {total_tests} total tests")

        return {
            "test_sets": results,
            "total_test_sets": len(results),
            "total_tests": total_tests,
            "garak_version": self._garak_version,
        }

    def _build_garak_metadata(self, probe: GarakProbeInfo) -> Dict[str, Any]:
        """Build Garak-specific metadata for a test set."""
        now = datetime.utcnow().isoformat()
        return {
            "source": "garak",
            "garak_version": self._garak_version,
            "garak_probe_class": probe.class_name,
            "garak_module": probe.module_name,
            "garak_full_name": probe.full_name,
            "garak_detector": probe.detector,
            "imported_at": now,
            "last_synced_at": now,
        }

    def _build_tests_data(
        self,
        probe: GarakProbeInfo,
        mapping: Any,  # GarakMapping
    ) -> List[test_set_schemas.TestData]:
        """
        Build test data list for bulk creation.

        Each prompt from the Garak probe becomes a test with proper
        category, behavior, topic, and metadata.
        """
        tests_data = []

        for idx, prompt_content in enumerate(probe.prompts):
            if not prompt_content or not prompt_content.strip():
                continue

            # Build test metadata
            test_metadata = {
                "source": "garak",
                "garak_probe_id": f"{probe.full_name}.{idx}",
                "garak_probe_class": probe.class_name,
                "garak_module": probe.module_name,
                "garak_tags": probe.tags,
            }

            # Create test data with taxonomy mapping
            test_data = test_set_schemas.TestData(
                prompt=test_set_schemas.TestPrompt(
                    content=prompt_content,
                    language_code="en",
                ),
                behavior=mapping.behavior,
                category=mapping.category,
                topic=mapping.topic,
                test_type="Single-Turn",
                metadata=test_metadata,
            )
            tests_data.append(test_data)

        return tests_data

    def _get_probe_info(self, module_name: str, class_name: str) -> Optional[GarakProbeInfo]:
        """Get probe info for a specific probe class."""
        probes = self.probe_service.extract_probes_from_module(
            module_name, probe_class_names=[class_name]
        )
        return probes[0] if probes else None

    def _generate_test_set_name(self, probe: GarakProbeInfo, prefix: Optional[str]) -> str:
        """Generate a test set name from probe info."""
        prefix = prefix or "Garak"
        # Convert class name to readable format
        readable_name = probe.class_name.replace("_", " ")
        return f"{prefix}: {readable_name}"

    def _generate_description(self, probe: GarakProbeInfo, template: Optional[str]) -> str:
        """Generate test set description."""
        if template:
            return template.format(
                probe_name=probe.class_name,
                module_name=probe.module_name,
                full_name=probe.full_name,
            )
        return f"{probe.description} (from Garak {probe.full_name})"

    def _get_or_create_garak_metric(
        self,
        detector_class: str,
        organization_id: str,
        user_id: str,
    ) -> Metric:
        """
        Get or create a Garak detector metric.

        Args:
            detector_class: Full class path of the Garak detector
            organization_id: Organization ID
            user_id: User ID

        Returns:
            Metric model instance
        """
        org_uuid = UUID(organization_id)
        user_uuid = UUID(user_id)

        # Check if metric already exists for this detector
        existing_metric = (
            self.db.query(Metric)
            .filter(
                Metric.organization_id == org_uuid,
                Metric.class_name == self.GARAK_METRIC_CLASS_NAME,
            )
            .first()
        )

        # Check if this specific detector is already configured
        # We use a naming convention to identify Garak metrics
        metric_name = f"Garak: {detector_class.split('.')[-1]}"

        existing_metric = (
            self.db.query(Metric)
            .filter(
                Metric.organization_id == org_uuid,
                Metric.name == metric_name,
            )
            .first()
        )

        if existing_metric:
            return existing_metric

        # Create new Garak detector metric
        metric = Metric(
            id=uuid4(),
            name=metric_name,
            description=f"Garak detector: {detector_class}",
            evaluation_prompt=detector_class,  # Store detector class in evaluation_prompt
            score_type="categorical",
            categories=["pass", "fail"],
            passing_categories=["pass"],
            class_name=self.GARAK_METRIC_CLASS_NAME,
            organization_id=org_uuid,
            user_id=user_uuid,
        )

        self.db.add(metric)
        self.db.flush()

        logger.debug(f"Created Garak metric: {metric_name}")

        return metric

    def _associate_metric_with_test_set(
        self,
        test_set: TestSet,
        metric: Metric,
        organization_id: str,
        user_id: str,
    ) -> None:
        """Associate a metric with a test set."""
        org_uuid = UUID(organization_id)
        user_uuid = UUID(user_id)

        # Check if association already exists
        existing = self.db.execute(
            test_set_metric_association.select().where(
                test_set_metric_association.c.test_set_id == test_set.id,
                test_set_metric_association.c.metric_id == metric.id,
            )
        ).first()

        if not existing:
            self.db.execute(
                test_set_metric_association.insert().values(
                    test_set_id=test_set.id,
                    metric_id=metric.id,
                    organization_id=org_uuid,
                    user_id=user_uuid,
                )
            )

    def get_import_preview(
        self,
        probes: List[Any],  # List of GarakProbeSelection from schema
        name_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a preview of what would be imported.

        Args:
            probes: List of probe selections (module_name, class_name)
            name_prefix: Prefix for auto-generated test set names

        Returns:
            Dictionary with import preview information
        """
        probe_previews = []
        total_tests = 0
        detectors = set()

        for probe_selection in probes:
            probe_info = self._get_probe_info(
                probe_selection.module_name, probe_selection.class_name
            )

            if not probe_info:
                continue

            # Generate test set name
            test_set_name = probe_selection.custom_name or self._generate_test_set_name(
                probe_info, name_prefix
            )

            # Get detector
            detector = probe_info.detector
            if not detector:
                mapping = GarakTaxonomy.get_mapping(probe_info.module_name)
                detector = mapping.default_detector
            if detector:
                detectors.add(detector)

            probe_previews.append(
                {
                    "module_name": probe_info.module_name,
                    "class_name": probe_info.class_name,
                    "full_name": probe_info.full_name,
                    "test_set_name": test_set_name,
                    "prompt_count": probe_info.prompt_count,
                    "detector": detector,
                }
            )
            total_tests += probe_info.prompt_count

        return {
            "garak_version": self.probe_service.garak_version,
            "total_test_sets": len(probe_previews),
            "total_tests": total_tests,
            "detector_count": len(detectors),
            "detectors": list(detectors),
            "probes": probe_previews,
        }
