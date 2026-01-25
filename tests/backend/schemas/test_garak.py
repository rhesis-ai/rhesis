"""Tests for Garak API schemas."""

import pytest

from rhesis.backend.app.schemas.garak import (
    GarakErrorResponse,
    GarakImportedTestSet,
    GarakImportPreviewResponse,
    GarakImportRequest,
    GarakImportResponse,
    GarakProbeClassResponse,
    GarakProbeDetailResponse,
    GarakProbeModuleResponse,
    GarakProbePreview,
    GarakProbeSelection,
    GarakProbesListResponse,
    GarakSyncPreviewResponse,
    GarakSyncResponse,
)


@pytest.mark.unit
class TestGarakProbeClassResponse:
    """Tests for GarakProbeClassResponse schema."""

    def test_probe_class_response_creation(self):
        """Test creating a probe class response."""
        response = GarakProbeClassResponse(
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            module_name="dan",
            description="DAN jailbreak probe",
            prompt_count=50,
            tags=["jailbreak", "dan"],
            detector="garak.detectors.mitigation.MitigationBypass",
        )

        assert response.class_name == "Dan_11_0"
        assert response.full_name == "dan.Dan_11_0"
        assert response.module_name == "dan"
        assert response.prompt_count == 50
        assert len(response.tags) == 2

    def test_probe_class_response_defaults(self):
        """Test probe class response with defaults."""
        response = GarakProbeClassResponse(
            class_name="Test",
            full_name="test.Test",
            module_name="test",
            description="Test probe",
            prompt_count=0,
        )

        assert response.tags == []
        assert response.detector is None


@pytest.mark.unit
class TestGarakProbeModuleResponse:
    """Tests for GarakProbeModuleResponse schema."""

    def test_probe_module_response_creation(self):
        """Test creating a probe module response."""
        probe = GarakProbeClassResponse(
            class_name="Test",
            full_name="test.Test",
            module_name="test",
            description="Test",
            prompt_count=10,
        )

        response = GarakProbeModuleResponse(
            name="dan",
            description="DAN jailbreak probes",
            probe_count=5,
            total_prompt_count=100,
            tags=["jailbreak"],
            default_detector="garak.detectors.mitigation.MitigationBypass",
            rhesis_category="Harmful",
            rhesis_topic="Jailbreak",
            rhesis_behavior="Robustness",
            probes=[probe],
        )

        assert response.name == "dan"
        assert response.probe_count == 5
        assert response.total_prompt_count == 100
        assert response.rhesis_category == "Harmful"
        assert len(response.probes) == 1


@pytest.mark.unit
class TestGarakProbesListResponse:
    """Tests for GarakProbesListResponse schema."""

    def test_probes_list_response_creation(self):
        """Test creating a probes list response."""
        response = GarakProbesListResponse(
            garak_version="0.9.5",
            modules=[],
            total_modules=0,
        )

        assert response.garak_version == "0.9.5"
        assert response.total_modules == 0
        assert response.modules == []


@pytest.mark.unit
class TestGarakProbeDetailResponse:
    """Tests for GarakProbeDetailResponse schema."""

    def test_probe_detail_response_creation(self):
        """Test creating a probe detail response."""
        response = GarakProbeDetailResponse(
            name="dan",
            description="DAN probes",
            probe_classes=["Dan_11_0", "Dan_10_0"],
            probe_count=2,
            total_prompt_count=100,
            tags=["jailbreak"],
            default_detector="garak.detectors.mitigation.MitigationBypass",
            rhesis_mapping={
                "category": "Harmful",
                "topic": "Jailbreak",
                "behavior": "Robustness",
            },
            probes=[{"class_name": "Dan_11_0"}],
        )

        assert response.name == "dan"
        assert len(response.probe_classes) == 2
        assert response.rhesis_mapping["category"] == "Harmful"


@pytest.mark.unit
class TestGarakProbeSelection:
    """Tests for GarakProbeSelection schema."""

    def test_probe_selection_creation(self):
        """Test creating a probe selection."""
        selection = GarakProbeSelection(
            module_name="dan",
            class_name="Dan_11_0",
            custom_name="My Custom Name",
        )

        assert selection.module_name == "dan"
        assert selection.class_name == "Dan_11_0"
        assert selection.custom_name == "My Custom Name"

    def test_probe_selection_without_custom_name(self):
        """Test probe selection without custom name."""
        selection = GarakProbeSelection(
            module_name="dan",
            class_name="Dan_11_0",
        )

        assert selection.custom_name is None


@pytest.mark.unit
class TestGarakImportRequest:
    """Tests for GarakImportRequest schema."""

    def test_import_request_creation(self):
        """Test creating an import request."""
        selection = GarakProbeSelection(
            module_name="dan",
            class_name="Dan_11_0",
        )

        request = GarakImportRequest(
            probes=[selection],
            name_prefix="Security",
            description_template="Test {probe_name}",
        )

        assert len(request.probes) == 1
        assert request.name_prefix == "Security"
        assert request.description_template == "Test {probe_name}"

    def test_import_request_defaults(self):
        """Test import request with defaults."""
        selection = GarakProbeSelection(
            module_name="dan",
            class_name="Dan_11_0",
        )

        request = GarakImportRequest(probes=[selection])

        assert request.name_prefix == "Garak"
        assert request.description_template is None

    def test_import_request_requires_probes(self):
        """Test import request requires at least one probe."""
        with pytest.raises(ValueError):
            GarakImportRequest(probes=[])


@pytest.mark.unit
class TestGarakProbePreview:
    """Tests for GarakProbePreview schema."""

    def test_probe_preview_creation(self):
        """Test creating a probe preview."""
        preview = GarakProbePreview(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            test_set_name="Garak: Dan 11 0",
            prompt_count=50,
            detector="garak.detectors.mitigation.MitigationBypass",
        )

        assert preview.module_name == "dan"
        assert preview.prompt_count == 50
        assert preview.detector is not None


@pytest.mark.unit
class TestGarakImportPreviewResponse:
    """Tests for GarakImportPreviewResponse schema."""

    def test_import_preview_response_creation(self):
        """Test creating an import preview response."""
        probe = GarakProbePreview(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            test_set_name="Garak: Dan 11 0",
            prompt_count=50,
        )

        response = GarakImportPreviewResponse(
            garak_version="0.9.5",
            total_test_sets=1,
            total_tests=50,
            detector_count=1,
            detectors=["garak.detectors.mitigation.MitigationBypass"],
            probes=[probe],
        )

        assert response.garak_version == "0.9.5"
        assert response.total_test_sets == 1
        assert response.total_tests == 50


@pytest.mark.unit
class TestGarakImportedTestSet:
    """Tests for GarakImportedTestSet schema."""

    def test_imported_test_set_creation(self):
        """Test creating an imported test set response."""
        imported = GarakImportedTestSet(
            test_set_id="123e4567-e89b-12d3-a456-426614174000",
            test_set_name="Garak: Dan 11 0",
            probe_full_name="dan.Dan_11_0",
            test_count=50,
        )

        assert imported.test_set_id == "123e4567-e89b-12d3-a456-426614174000"
        assert imported.test_count == 50


@pytest.mark.unit
class TestGarakImportResponse:
    """Tests for GarakImportResponse schema."""

    def test_import_response_creation(self):
        """Test creating an import response."""
        test_set = GarakImportedTestSet(
            test_set_id="123",
            test_set_name="Test",
            probe_full_name="dan.Dan_11_0",
            test_count=50,
        )

        response = GarakImportResponse(
            test_sets=[test_set],
            total_test_sets=1,
            total_tests=50,
            garak_version="0.9.5",
        )

        assert len(response.test_sets) == 1
        assert response.total_test_sets == 1


@pytest.mark.unit
class TestGarakSyncPreviewResponse:
    """Tests for GarakSyncPreviewResponse schema."""

    def test_sync_preview_response_creation(self):
        """Test creating a sync preview response."""
        response = GarakSyncPreviewResponse(
            can_sync=True,
            old_version="0.9.0",
            new_version="0.9.5",
            to_add=5,
            to_remove=2,
            unchanged=10,
            probe_class="Dan_11_0",
            module_name="dan",
        )

        assert response.can_sync is True
        assert response.old_version == "0.9.0"
        assert response.new_version == "0.9.5"
        assert response.to_add == 5
        assert response.to_remove == 2
        assert response.unchanged == 10

    def test_sync_preview_response_with_error(self):
        """Test creating a sync preview response with error."""
        response = GarakSyncPreviewResponse(
            can_sync=False,
            old_version="0.9.0",
            new_version="0.9.5",
            to_add=0,
            to_remove=0,
            unchanged=0,
            error="Probe not found",
        )

        assert response.can_sync is False
        assert response.error == "Probe not found"

    def test_sync_preview_response_legacy_modules(self):
        """Test sync preview response with legacy modules format."""
        response = GarakSyncPreviewResponse(
            can_sync=True,
            old_version="0.9.0",
            new_version="0.9.5",
            to_add=10,
            to_remove=5,
            unchanged=100,
            modules=["dan", "encoding", "xss"],
        )

        assert response.modules == ["dan", "encoding", "xss"]


@pytest.mark.unit
class TestGarakSyncResponse:
    """Tests for GarakSyncResponse schema."""

    def test_sync_response_creation(self):
        """Test creating a sync response."""
        response = GarakSyncResponse(
            added=5,
            removed=2,
            unchanged=10,
            new_garak_version="0.9.5",
            old_garak_version="0.9.0",
        )

        assert response.added == 5
        assert response.removed == 2
        assert response.unchanged == 10
        assert response.new_garak_version == "0.9.5"
        assert response.old_garak_version == "0.9.0"


@pytest.mark.unit
class TestGarakErrorResponse:
    """Tests for GarakErrorResponse schema."""

    def test_error_response_creation(self):
        """Test creating an error response."""
        response = GarakErrorResponse(
            error="Something went wrong",
            detail="More details about the error",
        )

        assert response.error == "Something went wrong"
        assert response.detail == "More details about the error"

    def test_error_response_without_detail(self):
        """Test error response without detail."""
        response = GarakErrorResponse(error="Simple error")

        assert response.error == "Simple error"
        assert response.detail is None
