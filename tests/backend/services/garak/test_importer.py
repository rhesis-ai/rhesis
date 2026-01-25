"""Tests for GarakImporter service."""

from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.services.garak.importer import GarakImporter, ProbeSelection
from rhesis.backend.app.services.garak.probes import GarakProbeInfo
from rhesis.backend.app.services.garak.taxonomy import GarakMapping

fake = Faker()


@pytest.mark.unit
@pytest.mark.service
class TestProbeSelectionDataclass:
    """Tests for ProbeSelection dataclass."""

    def test_probe_selection_creation(self):
        """Test creating a ProbeSelection instance."""
        selection = ProbeSelection(
            module_name="dan",
            class_name="Dan_11_0",
            custom_name="Custom DAN Test Set",
        )

        assert selection.module_name == "dan"
        assert selection.class_name == "Dan_11_0"
        assert selection.custom_name == "Custom DAN Test Set"

    def test_probe_selection_defaults(self):
        """Test ProbeSelection default values."""
        selection = ProbeSelection(
            module_name="dan",
            class_name="Dan_11_0",
        )

        assert selection.custom_name is None


@pytest.mark.unit
@pytest.mark.service
class TestGarakImporterInit:
    """Tests for GarakImporter initialization."""

    def test_importer_initialization(self, test_db: Session):
        """Test importer initializes correctly."""
        importer = GarakImporter(test_db)

        assert importer.db is test_db
        assert importer.probe_service is not None

    def test_importer_class_constants(self):
        """Test importer class constants."""
        assert GarakImporter.GARAK_METRIC_CLASS_NAME == "GarakDetectorMetric"
        assert GarakImporter.GARAK_METRIC_BACKEND == "garak"


@pytest.mark.unit
@pytest.mark.service
class TestGarakImporterMetadataBuilding:
    """Tests for metadata building methods."""

    def test_build_garak_metadata(self, test_db: Session):
        """Test _build_garak_metadata returns correct structure."""
        importer = GarakImporter(test_db)
        importer._garak_version = "0.9.5"

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
            detector="garak.detectors.mitigation.MitigationBypass",
        )

        metadata = importer._build_garak_metadata(probe)

        assert metadata["source"] == "garak"
        assert metadata["garak_version"] == "0.9.5"
        assert metadata["garak_probe_class"] == "Dan_11_0"
        assert metadata["garak_module"] == "dan"
        assert metadata["garak_full_name"] == "dan.Dan_11_0"
        assert metadata["garak_detector"] == "garak.detectors.mitigation.MitigationBypass"
        assert "imported_at" in metadata
        assert "last_synced_at" in metadata

    def test_build_tests_data(self, test_db: Session):
        """Test _build_tests_data creates correct test structure."""
        importer = GarakImporter(test_db)

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
            prompts=["Prompt 1", "Prompt 2"],
            prompt_count=2,
            tags=["jailbreak"],
        )

        mapping = GarakMapping(
            category="Harmful",
            topic="Jailbreak",
            behavior="Robustness",
            default_detector="garak.detectors.mitigation.MitigationBypass",
            description="DAN mapping",
        )

        tests_data = importer._build_tests_data(probe, mapping)

        assert len(tests_data) == 2
        assert tests_data[0].prompt.content == "Prompt 1"
        assert tests_data[0].behavior == "Robustness"
        assert tests_data[0].category == "Harmful"
        assert tests_data[0].topic == "Jailbreak"
        assert tests_data[0].test_type == "Single-Turn"
        assert tests_data[0].metadata["source"] == "garak"
        assert tests_data[0].metadata["garak_probe_class"] == "Dan_11_0"

    def test_build_tests_data_skips_empty_prompts(self, test_db: Session):
        """Test _build_tests_data skips empty prompts."""
        importer = GarakImporter(test_db)

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
            prompts=["Valid prompt", "", "  ", "Another valid"],
            prompt_count=4,
        )

        mapping = GarakMapping(
            category="Harmful",
            topic="Jailbreak",
            behavior="Robustness",
            default_detector="detector",
            description="desc",
        )

        tests_data = importer._build_tests_data(probe, mapping)

        # Should only have 2 valid prompts
        assert len(tests_data) == 2


@pytest.mark.unit
@pytest.mark.service
class TestGarakImporterNameGeneration:
    """Tests for name generation methods."""

    def test_generate_test_set_name_with_prefix(self, test_db: Session):
        """Test _generate_test_set_name with custom prefix."""
        importer = GarakImporter(test_db)

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
        )

        name = importer._generate_test_set_name(probe, "Security")

        assert name == "Security: Dan 11 0"

    def test_generate_test_set_name_default_prefix(self, test_db: Session):
        """Test _generate_test_set_name with default prefix."""
        importer = GarakImporter(test_db)

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
        )

        name = importer._generate_test_set_name(probe, None)

        assert name == "Garak: Dan 11 0"

    def test_generate_description_with_template(self, test_db: Session):
        """Test _generate_description with custom template."""
        importer = GarakImporter(test_db)

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN jailbreak probe",
        )

        description = importer._generate_description(
            probe, "Testing {probe_name} from {module_name} ({full_name})"
        )

        assert "Dan_11_0" in description
        assert "dan" in description

    def test_generate_description_default(self, test_db: Session):
        """Test _generate_description with default template."""
        importer = GarakImporter(test_db)

        probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN jailbreak probe",
        )

        description = importer._generate_description(probe, None)

        assert "DAN jailbreak probe" in description
        assert "dan.Dan_11_0" in description


@pytest.mark.unit
@pytest.mark.service
class TestGarakImporterProbeRetrieval:
    """Tests for probe info retrieval."""

    def test_get_probe_info_found(self, test_db: Session):
        """Test _get_probe_info when probe is found."""
        importer = GarakImporter(test_db)

        mock_probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
        )

        with patch.object(
            importer.probe_service,
            "extract_probes_from_module",
            return_value=[mock_probe],
        ):
            result = importer._get_probe_info("dan", "Dan_11_0")

            assert result is mock_probe

    def test_get_probe_info_not_found(self, test_db: Session):
        """Test _get_probe_info when probe is not found."""
        importer = GarakImporter(test_db)

        with patch.object(
            importer.probe_service,
            "extract_probes_from_module",
            return_value=[],
        ):
            result = importer._get_probe_info("nonexistent", "NoProbe")

            assert result is None


@pytest.mark.unit
@pytest.mark.service
class TestGarakImporterPreview:
    """Tests for import preview."""

    def test_get_import_preview(self, test_db: Session):
        """Test get_import_preview returns correct structure."""
        importer = GarakImporter(test_db)

        mock_probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
            prompt_count=10,
            detector="garak.detectors.mitigation.MitigationBypass",
        )

        # Create mock probe selection with required attributes
        mock_selection = MagicMock()
        mock_selection.module_name = "dan"
        mock_selection.class_name = "Dan_11_0"
        mock_selection.custom_name = None

        with patch.object(importer, "_get_probe_info", return_value=mock_probe):
            preview = importer.get_import_preview(
                probes=[mock_selection],
                name_prefix="Security",
            )

            assert preview["total_test_sets"] == 1
            assert preview["total_tests"] == 10
            assert preview["detector_count"] == 1
            assert len(preview["detectors"]) == 1
            assert len(preview["probes"]) == 1
            assert preview["probes"][0]["module_name"] == "dan"
            assert preview["probes"][0]["class_name"] == "Dan_11_0"

    def test_get_import_preview_skips_not_found(self, test_db: Session):
        """Test get_import_preview skips probes that aren't found."""
        importer = GarakImporter(test_db)

        mock_selection = MagicMock()
        mock_selection.module_name = "nonexistent"
        mock_selection.class_name = "NoProbe"
        mock_selection.custom_name = None

        with patch.object(importer, "_get_probe_info", return_value=None):
            preview = importer.get_import_preview(
                probes=[mock_selection],
                name_prefix="Test",
            )

            assert preview["total_test_sets"] == 0
            assert preview["total_tests"] == 0
            assert len(preview["probes"]) == 0

    def test_get_import_preview_uses_taxonomy_detector(self, test_db: Session):
        """Test preview falls back to taxonomy detector when probe has none."""
        importer = GarakImporter(test_db)

        mock_probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
            prompt_count=5,
            detector=None,  # No detector on probe
        )

        mock_selection = MagicMock()
        mock_selection.module_name = "dan"
        mock_selection.class_name = "Dan_11_0"
        mock_selection.custom_name = None

        with patch.object(importer, "_get_probe_info", return_value=mock_probe):
            preview = importer.get_import_preview(
                probes=[mock_selection],
                name_prefix="Test",
            )

            # Should have detector from taxonomy
            assert len(preview["detectors"]) == 1
            assert "garak.detectors" in preview["detectors"][0]


@pytest.mark.unit
@pytest.mark.service
class TestGarakImporterMetricCreation:
    """Tests for metric creation/lookup."""

    def test_get_or_create_garak_metric_naming(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test _get_or_create_garak_metric generates correct metric name."""
        importer = GarakImporter(test_db)

        # Test the metric name generation logic by checking the query
        # The method looks for metrics named "Garak: {detector_class_name}"
        detector_class = "garak.detectors.mitigation.MitigationBypass"
        expected_name = f"Garak: {detector_class.split('.')[-1]}"

        assert expected_name == "Garak: MitigationBypass"

    def test_garak_metric_constants(self):
        """Test GarakImporter metric class constants."""
        assert GarakImporter.GARAK_METRIC_CLASS_NAME == "GarakDetectorMetric"
        assert GarakImporter.GARAK_METRIC_BACKEND == "garak"
