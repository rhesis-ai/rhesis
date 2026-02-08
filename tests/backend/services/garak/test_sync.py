"""Tests for GarakSyncService."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.services.garak.probes import GarakProbeInfo
from rhesis.backend.app.services.garak.sync import GarakSyncService, SyncResult

fake = Faker()


@pytest.mark.unit
@pytest.mark.service
class TestSyncResultDataclass:
    """Tests for SyncResult dataclass."""

    def test_sync_result_creation(self):
        """Test creating a SyncResult instance."""
        result = SyncResult(
            added=5,
            removed=2,
            unchanged=10,
            new_garak_version="0.9.5",
            old_garak_version="0.9.0",
        )

        assert result.added == 5
        assert result.removed == 2
        assert result.unchanged == 10
        assert result.new_garak_version == "0.9.5"
        assert result.old_garak_version == "0.9.0"


@pytest.mark.unit
@pytest.mark.service
class TestGarakSyncServiceInit:
    """Tests for GarakSyncService initialization."""

    def test_sync_service_initialization(self, test_db: Session):
        """Test sync service initializes correctly."""
        service = GarakSyncService(test_db)

        assert service.db is test_db
        assert service.probe_service is not None


@pytest.mark.unit
@pytest.mark.service
class TestGarakSyncServiceCanSync:
    """Tests for can_sync method."""

    def test_can_sync_with_garak_test_set(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Test can_sync returns True for Garak test sets."""
        service = GarakSyncService(test_db)

        # Create a Garak test set
        test_set = TestSet(
            name="Garak Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={
                "source": "garak",
                "garak_module": "dan",
                "garak_probe_class": "Dan_11_0",
            },
        )
        test_db.add(test_set)
        test_db.commit()

        result = service.can_sync(str(test_set.id), str(test_org_id))

        assert result is True

    def test_can_sync_with_non_garak_test_set(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Test can_sync returns False for non-Garak test sets."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="Regular Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"source": "manual"},
        )
        test_db.add(test_set)
        test_db.commit()

        result = service.can_sync(str(test_set.id), str(test_org_id))

        assert result is False

    def test_can_sync_with_no_attributes(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Test can_sync returns False for test sets without attributes."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="No Attributes Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()

        result = service.can_sync(str(test_set.id), str(test_org_id))

        assert result is False

    def test_can_sync_test_set_not_found(self, test_db: Session, test_org_id):
        """Test can_sync returns False for non-existent test set."""
        service = GarakSyncService(test_db)

        result = service.can_sync(str(uuid4()), str(test_org_id))

        assert result is False


@pytest.mark.unit
@pytest.mark.service
class TestGarakSyncServiceProbeIds:
    """Tests for probe ID extraction."""

    def test_get_existing_probe_ids(self, test_db: Session, test_org_id, authenticated_user_id):
        """Test _get_existing_probe_ids extracts probe IDs correctly."""
        service = GarakSyncService(test_db)

        # Create test set with tests
        test_set = TestSet(
            name="Garak Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"source": "garak"},
        )
        test_db.add(test_set)
        test_db.commit()

        # Create tests with garak metadata
        test1 = Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            test_metadata={
                "source": "garak",
                "garak_probe_id": "dan.Dan_11_0.0",
            },
        )
        test2 = Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            test_metadata={
                "source": "garak",
                "garak_probe_id": "dan.Dan_11_0.1",
            },
        )
        test_db.add_all([test1, test2])
        test_db.commit()

        # Associate tests with test set
        test_set.tests.append(test1)
        test_set.tests.append(test2)
        test_db.commit()

        probe_ids = service._get_existing_probe_ids(test_set)

        assert len(probe_ids) == 2
        assert "dan.Dan_11_0.0" in probe_ids
        assert "dan.Dan_11_0.1" in probe_ids

    def test_get_existing_probe_ids_ignores_non_garak_tests(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Test _get_existing_probe_ids ignores non-garak tests."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="Garak Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"source": "garak"},
        )
        test_db.add(test_set)
        test_db.commit()

        # Create a non-garak test
        test1 = Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            test_metadata={"source": "manual"},
        )
        test_db.add(test1)
        test_db.commit()

        test_set.tests.append(test1)
        test_db.commit()

        probe_ids = service._get_existing_probe_ids(test_set)

        assert len(probe_ids) == 0


@pytest.mark.unit
@pytest.mark.service
class TestGarakSyncServiceSyncTestSet:
    """Tests for sync_test_set method."""

    def test_sync_test_set_not_found(self, test_db: Session, test_org_id, authenticated_user_id):
        """Test sync_test_set raises error for non-existent test set."""
        service = GarakSyncService(test_db)

        with pytest.raises(ValueError, match="Test set not found"):
            service.sync_test_set(
                test_set_id=str(uuid4()),
                organization_id=str(test_org_id),
                user_id=str(authenticated_user_id),
            )

    def test_sync_test_set_not_garak(self, test_db: Session, test_org_id, authenticated_user_id):
        """Test sync_test_set raises error for non-Garak test sets."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="Regular Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"source": "manual"},
        )
        test_db.add(test_set)
        test_db.commit()

        with pytest.raises(ValueError, match="not a Garak-imported test set"):
            service.sync_test_set(
                test_set_id=str(test_set.id),
                organization_id=str(test_org_id),
                user_id=str(authenticated_user_id),
            )


@pytest.mark.unit
@pytest.mark.service
class TestGarakSyncServiceSyncPreview:
    """Tests for get_sync_preview method."""

    def test_get_sync_preview_not_found(self, test_db: Session, test_org_id):
        """Test get_sync_preview returns None for non-existent test set."""
        service = GarakSyncService(test_db)

        result = service.get_sync_preview(
            test_set_id=str(uuid4()),
            organization_id=str(test_org_id),
        )

        assert result is None

    def test_get_sync_preview_non_garak(self, test_db: Session, test_org_id, authenticated_user_id):
        """Test get_sync_preview returns None for non-Garak test sets."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="Regular Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"source": "manual"},
        )
        test_db.add(test_set)
        test_db.commit()

        result = service.get_sync_preview(
            test_set_id=str(test_set.id),
            organization_id=str(test_org_id),
        )

        assert result is None

    def test_get_sync_preview_no_attributes(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Test get_sync_preview returns None for test sets without attributes."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="No Attributes",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()

        result = service.get_sync_preview(
            test_set_id=str(test_set.id),
            organization_id=str(test_org_id),
        )

        assert result is None

    def test_get_sync_preview_probe_not_found(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Test get_sync_preview handles probe not found."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="Garak Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={
                "source": "garak",
                "garak_module": "nonexistent",
                "garak_probe_class": "NoProbe",
                "garak_version": "0.9.0",
            },
        )
        test_db.add(test_set)
        test_db.commit()

        with patch.object(service, "_get_probe", return_value=None):
            result = service.get_sync_preview(
                test_set_id=str(test_set.id),
                organization_id=str(test_org_id),
            )

            assert result["can_sync"] is False
            assert "error" in result

    def test_get_sync_preview_success(self, test_db: Session, test_org_id, authenticated_user_id):
        """Test get_sync_preview returns correct structure."""
        service = GarakSyncService(test_db)

        test_set = TestSet(
            name="Garak Test Set",
            description="Test",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={
                "source": "garak",
                "garak_module": "dan",
                "garak_probe_class": "Dan_11_0",
                "garak_version": "0.9.0",
                "last_synced_at": "2024-01-01T00:00:00",
            },
        )
        test_db.add(test_set)
        test_db.commit()

        mock_probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
            prompts=["prompt1", "prompt2", "prompt3"],
            prompt_count=3,
        )

        with patch.object(service, "_get_probe", return_value=mock_probe):
            # Need to mock the garak_version property
            with patch.object(
                type(service.probe_service), "garak_version", property(lambda self: "0.9.5")
            ):
                result = service.get_sync_preview(
                    test_set_id=str(test_set.id),
                    organization_id=str(test_org_id),
                )

                assert result["can_sync"] is True
                assert result["old_version"] == "0.9.0"
                assert result["probe_class"] == "Dan_11_0"
                assert result["module_name"] == "dan"
                assert "to_add" in result
                assert "to_remove" in result
                assert "unchanged" in result


@pytest.mark.unit
@pytest.mark.service
class TestGarakSyncServiceGetProbe:
    """Tests for _get_probe helper method."""

    def test_get_probe_found(self, test_db: Session):
        """Test _get_probe when probe is found."""
        service = GarakSyncService(test_db)

        mock_probe = GarakProbeInfo(
            module_name="dan",
            class_name="Dan_11_0",
            full_name="dan.Dan_11_0",
            description="DAN probe",
        )

        with patch.object(
            service.probe_service,
            "extract_probes_from_module",
            return_value=[mock_probe],
        ):
            result = service._get_probe("dan", "Dan_11_0")

            assert result is mock_probe

    def test_get_probe_not_found(self, test_db: Session):
        """Test _get_probe when probe is not found."""
        service = GarakSyncService(test_db)

        with patch.object(
            service.probe_service,
            "extract_probes_from_module",
            return_value=[],
        ):
            result = service._get_probe("nonexistent", "NoProbe")

            assert result is None
