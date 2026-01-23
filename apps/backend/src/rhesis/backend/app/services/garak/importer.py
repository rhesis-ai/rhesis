"""
Garak probe importer service.

This module handles the import of Garak probes as Rhesis test sets,
including metric creation and association.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_set import TestSet, test_set_metric_association
from rhesis.backend.logging.rhesis_logger import logger

from .probes import GarakProbeInfo, GarakProbeService
from .taxonomy import GarakTaxonomy


class GarakImporter:
    """Service for importing Garak probes as Rhesis test sets."""

    # Garak detector metric class name for SDK
    GARAK_METRIC_CLASS_NAME = "GarakDetectorMetric"
    GARAK_METRIC_BACKEND = "garak"

    def __init__(self, db: Session):
        self.db = db
        self.probe_service = GarakProbeService()

    def import_probes_as_test_set(
        self,
        modules: List[str],
        test_set_name: str,
        organization_id: str,
        user_id: str,
        description: Optional[str] = None,
    ) -> TestSet:
        """
        Import selected Garak probe modules as a Rhesis test set.

        Args:
            modules: List of Garak module names to import
            test_set_name: Name for the new test set
            organization_id: Organization ID
            user_id: User ID
            description: Optional description for the test set

        Returns:
            Created TestSet model instance
        """
        logger.info(f"Importing Garak probes from modules: {modules}")

        # Collect all probes from selected modules
        all_probes: List[GarakProbeInfo] = []
        all_detectors: set = set()

        for module_name in modules:
            probes = self.probe_service.extract_probes_from_module(module_name)
            all_probes.extend(probes)

            # Collect unique detectors
            mapping = GarakTaxonomy.get_mapping(module_name)
            all_detectors.add(mapping.default_detector)

        if not all_probes:
            raise ValueError(f"No probes found in modules: {modules}")

        # Create the test set
        test_set = self._create_test_set(
            name=test_set_name,
            description=description,
            modules=modules,
            organization_id=organization_id,
            user_id=user_id,
        )

        # Create tests for each probe/prompt
        tests = self._create_tests_from_probes(
            probes=all_probes,
            test_set=test_set,
            organization_id=organization_id,
            user_id=user_id,
        )

        # Create and associate Garak detector metrics
        for detector_class in all_detectors:
            metric = self._get_or_create_garak_metric(
                detector_class=detector_class,
                organization_id=organization_id,
                user_id=user_id,
            )
            self._associate_metric_with_test_set(test_set, metric, organization_id, user_id)

        self.db.commit()

        logger.info(
            f"Created test set '{test_set_name}' with {len(tests)} tests "
            f"and {len(all_detectors)} metrics"
        )

        return test_set

    def _create_test_set(
        self,
        name: str,
        description: Optional[str],
        modules: List[str],
        organization_id: str,
        user_id: str,
    ) -> TestSet:
        """Create a new test set for Garak probes."""
        garak_version = self.probe_service.garak_version
        now = datetime.utcnow().isoformat()

        # Build attributes with Garak metadata
        attributes = {
            "source": "garak",
            "garak_version": garak_version,
            "garak_modules": modules,
            "imported_at": now,
            "last_synced_at": now,
        }

        # Get primary module for category/topic/behavior
        primary_module = modules[0] if modules else "unknown"
        mapping = GarakTaxonomy.get_mapping(primary_module)

        # Generate description if not provided
        if not description:
            module_list = ", ".join(modules)
            description = f"Garak probes imported from: {module_list}"

        test_set = TestSet(
            id=uuid4(),
            name=name,
            description=description,
            attributes=attributes,
            visibility="organization",
            is_published=False,
            organization_id=UUID(organization_id),
            user_id=UUID(user_id),
        )

        self.db.add(test_set)
        self.db.flush()  # Get the ID

        return test_set

    def _create_tests_from_probes(
        self,
        probes: List[GarakProbeInfo],
        test_set: TestSet,
        organization_id: str,
        user_id: str,
    ) -> List[Test]:
        """Create Test entities from Garak probes."""
        tests = []
        org_uuid = UUID(organization_id)
        user_uuid = UUID(user_id)

        for probe in probes:
            mapping = GarakTaxonomy.get_mapping(probe.module_name)

            # Create a test for each prompt in the probe
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

                test = Test(
                    id=uuid4(),
                    organization_id=org_uuid,
                    user_id=user_uuid,
                    test_metadata=test_metadata,
                )

                # Create associated prompt
                from rhesis.backend.app.models.prompt import Prompt

                prompt = Prompt(
                    id=uuid4(),
                    content=prompt_content,
                    organization_id=org_uuid,
                    user_id=user_uuid,
                )
                self.db.add(prompt)
                self.db.flush()

                test.prompt_id = prompt.id

                self.db.add(test)
                tests.append(test)

        self.db.flush()

        # Associate tests with test set
        from rhesis.backend.app.models.test import test_test_set_association

        for test in tests:
            self.db.execute(
                test_test_set_association.insert().values(
                    test_id=test.id,
                    test_set_id=test_set.id,
                    organization_id=org_uuid,
                    user_id=user_uuid,
                )
            )

        return tests

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
        modules: List[str],
    ) -> Dict[str, Any]:
        """
        Get a preview of what would be imported.

        Args:
            modules: List of Garak module names

        Returns:
            Dictionary with import preview information
        """
        total_probes = 0
        total_prompts = 0
        detectors = set()
        module_details = []

        for module_name in modules:
            module_info = self.probe_service.get_probe_details(module_name)
            if module_info:
                probes = self.probe_service.extract_probes_from_module(module_name)
                prompt_count = sum(p.prompt_count for p in probes)

                total_probes += len(probes)
                total_prompts += prompt_count

                mapping = GarakTaxonomy.get_mapping(module_name)
                detectors.add(mapping.default_detector)

                module_details.append(
                    {
                        "name": module_name,
                        "probe_count": len(probes),
                        "prompt_count": prompt_count,
                        "category": mapping.category,
                        "topic": mapping.topic,
                        "behavior": mapping.behavior,
                    }
                )

        return {
            "garak_version": self.probe_service.garak_version,
            "total_probes": total_probes,
            "total_prompts": total_prompts,
            "total_tests": total_prompts,  # One test per prompt
            "detector_count": len(detectors),
            "detectors": list(detectors),
            "modules": module_details,
        }
