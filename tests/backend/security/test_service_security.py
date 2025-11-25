"""
🔒 Service Layer Security Tests

This module tests security vulnerabilities in various service layer components,
including tag management, test set services, and other service-level operations.
"""

import uuid
import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models, crud
from tests.backend.routes.fixtures.data_factories import TagDataFactory


@pytest.mark.security
class TestTagOrganizationSecurity:
    """Test that tag operations properly enforce organization-based security"""

    def test_get_tag_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_tag properly filters by organization"""
        import inspect

        # Verify that get_tag accepts organization_id parameter (tags may be organization-scoped)
        signature = inspect.signature(crud.get_tag)
        assert "organization_id" in signature.parameters, (
            "get_tag should accept organization_id for tag scoping"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Tag Org 1 {unique_id}",
            f"tag-user1-{unique_id}@security-test.com",
            "Tag User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Tag Org 2 {unique_id}",
            f"tag-user2-{unique_id}@security-test.com",
            "Tag User 2",
        )

        # Create a tag in org1 using the data factory
        tag_data = TagDataFactory.sample_data()
        tag_data["name"] = f"Security Test Tag {unique_id}"
        tag = crud.create_tag(
            test_db, tag_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to access the tag
        result_org1 = crud.get_tag(test_db, tag.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == tag.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the tag
        result_org2 = crud.get_tag(test_db, tag.id, organization_id=str(org2.id))
        assert result_org2 is None

        # Test without organization filtering (should fail due to security requirements)
        with pytest.raises(
            ValueError, match="organization_id is required for Tag but was not provided"
        ):
            crud.get_tag(test_db, tag.id)

    def test_create_tag_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_tag properly scopes tags to organizations"""
        import inspect

        # Verify that create_tag accepts organization_id parameter
        signature = inspect.signature(crud.create_tag)
        assert "organization_id" in signature.parameters, (
            "create_tag should accept organization_id for tag scoping"
        )

        # Create a test organization and user
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org, user, _ = create_test_organization_and_user(
            test_db, f"Tag Org {unique_id}", f"tag-user-{unique_id}@security-test.com", "Tag User"
        )

        # Create a tag with organization scoping using data factory
        tag_data = TagDataFactory.sample_data()
        tag_data["name"] = f"Security Test Tag {unique_id}"

        result = crud.create_tag(
            test_db, tag_data, organization_id=str(org.id), user_id=str(user.id)
        )

        # Verify the tag was created with correct organization scoping
        assert result is not None
        assert result.name == f"Security Test Tag {unique_id}"
        assert str(result.organization_id) == str(org.id)
        assert str(result.user_id) == str(user.id)

    def test_delete_tag_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_tag properly filters by organization"""
        import inspect

        # Verify that delete_tag accepts organization_id parameter
        signature = inspect.signature(crud.delete_tag)
        assert "organization_id" in signature.parameters, (
            "delete_tag should accept organization_id for tag scoping"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Tag Delete Org 1 {unique_id}",
            f"tag-delete-user1-{unique_id}@security-test.com",
            "Tag Delete User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Tag Delete Org 2 {unique_id}",
            f"tag-delete-user2-{unique_id}@security-test.com",
            "Tag Delete User 2",
        )

        # Create a tag in org1 using data factory
        tag_data = TagDataFactory.sample_data()
        tag_data["name"] = f"Tag to Delete {unique_id}"
        tag = crud.create_tag(
            test_db, tag_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to delete the tag
        result_org1 = crud.delete_tag(
            test_db, tag.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None  # Tag was found and deleted

        # Create another tag in org1 for the next test using data factory
        tag_data2 = TagDataFactory.sample_data()
        tag_data2["name"] = f"Tag to Delete 2 {unique_id}"
        tag2 = crud.create_tag(
            test_db, tag_data2, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org2 should NOT be able to delete the tag from org1
        result_org2 = crud.delete_tag(
            test_db, tag2.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None  # Tag was not found/deleted due to organization filtering


@pytest.mark.security
class TestTestSetOrganizationSecurity:
    """Test that test set operations properly enforce organization-based security"""

    def test_get_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_set properly filters by organization"""
        import inspect

        # Verify that get_test_set accepts organization_id parameter
        signature = inspect.signature(crud.get_test_set)
        assert "organization_id" in signature.parameters, (
            "get_test_set should accept organization_id for test set scoping"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Org 1 {unique_id}",
            f"testset-user1-{unique_id}@security-test.com",
            "TestSet User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Org 2 {unique_id}",
            f"testset-user2-{unique_id}@security-test.com",
            "TestSet User 2",
        )

        # Create a test set in org1 using proper data structure
        from faker import Faker

        fake = Faker()
        test_set = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name=f"Security Test Set {unique_id}",
            description=fake.text(max_nb_chars=200),
            is_published=False,
            visibility="organization",
        )
        test_db.add(test_set)
        test_db.commit()

        # User from org1 should be able to access the test set
        result_org1 = crud.get_test_set(
            test_db, test_set.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == test_set.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the test set
        result_org2 = crud.get_test_set(
            test_db, test_set.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

        # Without organization filtering, should fail due to security requirements
        with pytest.raises(
            ValueError, match="organization_id is required for TestSet but was not provided"
        ):
            crud.get_test_set(test_db, test_set.id)

    def test_create_test_set_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_test_set properly scopes test sets to organizations"""
        import inspect

        # Verify that create_test_set accepts organization_id parameter
        signature = inspect.signature(crud.create_test_set)
        assert "organization_id" in signature.parameters, (
            "create_test_set should accept organization_id for test set scoping"
        )

        # Create a test organization and user
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org, user, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Create Org {unique_id}",
            f"testset-create-user-{unique_id}@security-test.com",
            "TestSet Create User",
        )

        # Create a test set with organization scoping using proper data structure
        from faker import Faker

        fake = Faker()
        test_set_data = {
            "name": f"Security Test Set Create {unique_id}",
            "description": fake.text(max_nb_chars=200),
            "is_published": False,
            "visibility": "organization",
        }

        result = crud.create_test_set(
            test_db, test_set_data, organization_id=str(org.id), user_id=str(user.id)
        )

        # Verify the test set was created with correct organization scoping
        assert result is not None
        assert result.name == f"Security Test Set Create {unique_id}"
        assert str(result.organization_id) == str(org.id)
        assert str(result.user_id) == str(user.id)

    def test_delete_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_test_set properly filters by organization"""
        import inspect

        # Verify that delete_test_set accepts organization_id parameter
        signature = inspect.signature(crud.delete_test_set)
        assert "organization_id" in signature.parameters, (
            "delete_test_set should accept organization_id for test set scoping"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Delete Org 1 {unique_id}",
            f"testset-delete-user1-{unique_id}@security-test.com",
            "TestSet Delete User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Delete Org 2 {unique_id}",
            f"testset-delete-user2-{unique_id}@security-test.com",
            "TestSet Delete User 2",
        )

        # Create a test set in org1 using proper data structure
        from faker import Faker

        fake = Faker()
        test_set_data = {
            "name": f"TestSet to Delete {unique_id}",
            "description": fake.text(max_nb_chars=200),
            "is_published": False,
            "visibility": "organization",
        }
        test_set = crud.create_test_set(
            test_db, test_set_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to delete the test set
        result_org1 = crud.delete_test_set(
            test_db, test_set.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None  # Test set was found and deleted

        # Create another test set in org1 for the next test
        test_set_data2 = {
            "name": f"TestSet to Delete 2 {unique_id}",
            "description": fake.text(max_nb_chars=200),
            "is_published": False,
            "visibility": "organization",
        }
        test_set2 = crud.create_test_set(
            test_db, test_set_data2, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org2 should NOT be able to delete the test set from org1
        result_org2 = crud.delete_test_set(
            test_db, test_set2.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None  # Test set was not found/deleted due to organization filtering

    def test_update_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that update_test_set properly filters by organization"""
        import inspect

        # Verify that update_test_set accepts organization_id parameter
        signature = inspect.signature(crud.update_test_set)
        assert "organization_id" in signature.parameters, (
            "update_test_set should accept organization_id for test set scoping"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Update Org 1 {unique_id}",
            f"testset-update-user1-{unique_id}@security-test.com",
            "TestSet Update User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"TestSet Update Org 2 {unique_id}",
            f"testset-update-user2-{unique_id}@security-test.com",
            "TestSet Update User 2",
        )

        # Create a test set in org1 using proper data structure
        from faker import Faker

        fake = Faker()
        test_set_data = {
            "name": f"TestSet to Update {unique_id}",
            "description": fake.text(max_nb_chars=200),
            "is_published": False,
            "visibility": "organization",
        }
        test_set = crud.create_test_set(
            test_db, test_set_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to update the test set
        update_data = {"name": f"Updated TestSet {unique_id}"}
        result_org1 = crud.update_test_set(
            test_db, test_set.id, update_data, organization_id=str(org1.id)
        )
        assert result_org1 is not None
        assert result_org1.name == f"Updated TestSet {unique_id}"
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to update the test set from org1
        update_data2 = {"name": f"Should Not Update {unique_id}"}
        result_org2 = crud.update_test_set(
            test_db, test_set.id, update_data2, organization_id=str(org2.id)
        )
        assert result_org2 is None  # Test set was not found/updated due to organization filtering


@pytest.mark.security
class TestTestSetCrudSecurity:
    """Test that test set CRUD operations properly enforce organization isolation"""

    def test_get_test_sets_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_sets properly filters by organization"""
        import inspect

        # Verify that get_test_sets accepts organization_id parameter
        signature = inspect.signature(crud.get_test_sets)
        assert "organization_id" in signature.parameters, (
            "get_test_sets should accept organization_id for filtering"
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"TestSets Org 1 {unique_id}",
            f"testsets-user1-{unique_id}@security-test.com",
            "TestSets User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"TestSets Org 2 {unique_id}",
            f"testsets-user2-{unique_id}@security-test.com",
            "TestSets User 2",
        )

        # Create test sets in both organizations using proper data structure
        from faker import Faker

        fake = Faker()
        test_set1_org1 = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name=f"Test Set 1 Org 1 {unique_id}",
            description=fake.text(max_nb_chars=200),
            is_published=False,
            visibility="organization",
        )
        test_set2_org1 = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name=f"Test Set 2 Org 1 {unique_id}",
            description=fake.text(max_nb_chars=200),
            is_published=False,
            visibility="organization",
        )
        test_set1_org2 = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org2.id,
            user_id=user2.id,
            name=f"Test Set 1 Org 2 {unique_id}",
            description=fake.text(max_nb_chars=200),
            is_published=False,
            visibility="organization",
        )

        test_db.add_all([test_set1_org1, test_set2_org1, test_set1_org2])
        test_db.commit()

        # Get test sets for org1 - should return at least the 2 we created
        result_org1 = crud.get_test_sets(test_db, organization_id=str(org1.id))
        assert len(result_org1) >= 2  # At least the 2 we created, could be more from initial data
        assert all(str(ts.organization_id) == str(org1.id) for ts in result_org1)

        # Verify our specific test sets are in the results
        test_set_names_org1 = {ts.name for ts in result_org1}
        assert f"Test Set 1 Org 1 {unique_id}" in test_set_names_org1
        assert f"Test Set 2 Org 1 {unique_id}" in test_set_names_org1

        # Get test sets for org2 - should return at least the 1 we created
        result_org2 = crud.get_test_sets(test_db, organization_id=str(org2.id))
        assert len(result_org2) >= 1  # At least the 1 we created, could be more from initial data
        assert all(str(ts.organization_id) == str(org2.id) for ts in result_org2)

        # Verify our specific test set is in the results
        test_set_names_org2 = {ts.name for ts in result_org2}
        assert f"Test Set 1 Org 2 {unique_id}" in test_set_names_org2

        # Get test sets without organization filtering - should fail due to security requirements
        with pytest.raises(
            ValueError, match="organization_id is required for TestSet but was not provided"
        ):
            crud.get_test_sets(test_db)

    # Note: get_test_set_by_name function doesn't exist in crud.py, so this test is removed


@pytest.mark.security
class TestServiceSecurityValidation:
    """Test that service functions properly implement organization filtering and cross-tenant isolation"""

    def test_service_functions_accept_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Ensure all service-related functions accept organization filtering"""
        import inspect

        # List of service-related CRUD functions that should accept organization_id
        service_functions = [
            "get_tag",
            "create_tag",
            "delete_tag",
            "get_test_set",
            "create_test_set",
            "delete_test_set",
            "update_test_set",
            "get_test_sets",
            # Note: get_test_set_by_name function doesn't exist in crud.py
        ]

        for func_name in service_functions:
            if hasattr(crud, func_name):
                func = getattr(crud, func_name)
                signature = inspect.signature(func)
                assert "organization_id" in signature.parameters, (
                    f"{func_name} should accept organization_id parameter"
                )

    def test_service_cross_tenant_isolation(self, test_db: Session):
        """🔒 SECURITY: Test that service operations are properly isolated between organizations"""
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Isolation Org 1 {unique_id}",
            f"isolation-user1-{unique_id}@security-test.com",
            "Isolation User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Isolation Org 2 {unique_id}",
            f"isolation-user2-{unique_id}@security-test.com",
            "Isolation User 2",
        )

        # Test tag isolation - create tags with same name in different orgs
        tag_name = f"shared_tag_name_{unique_id}"

        # Create tag in org1
        tag_data1 = TagDataFactory.sample_data()
        tag_data1["name"] = tag_name
        tag_org1 = crud.create_tag(
            test_db, tag_data1, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # Create tag in org2 with same name
        tag_data2 = TagDataFactory.sample_data()
        tag_data2["name"] = tag_name
        tag_org2 = crud.create_tag(
            test_db, tag_data2, organization_id=str(org2.id), user_id=str(user2.id)
        )

        # When querying with org1 filter, should only return org1 tag
        result_org1 = crud.get_tag(test_db, tag_org1.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.organization_id == org1.id
        assert result_org1.name == tag_name

        # When querying with org2 filter, should only return org2 tag
        result_org2 = crud.get_tag(test_db, tag_org2.id, organization_id=str(org2.id))
        assert result_org2 is not None
        assert result_org2.organization_id == org2.id
        assert result_org2.name == tag_name

        # Cross-tenant access should be blocked
        result_cross1 = crud.get_tag(test_db, tag_org1.id, organization_id=str(org2.id))
        assert result_cross1 is None

        result_cross2 = crud.get_tag(test_db, tag_org2.id, organization_id=str(org1.id))
        assert result_cross2 is None
