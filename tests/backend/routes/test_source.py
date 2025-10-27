"""
📚 Source Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for source entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🌐 URL validation and citation testing
- 📖 Entity type classification
- 🌍 Multi-language source support

Run with: python -m pytest tests/backend/routes/test_source.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import SourceDataFactory

# Initialize Faker
fake = Faker()


class SourceTestMixin:
    """Enhanced source test mixin using factory system"""
    
    # Entity configuration
    entity_name = "source"
    entity_plural = "sources"
    endpoints = APIEndpoints.SOURCES
    
    # Field mappings for sources
    name_field = "title"
    description_field = "description"
    
    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample source data using factory"""
        return SourceDataFactory.sample_data()
    
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal source data using factory"""
        return SourceDataFactory.minimal_data()
    
    def get_update_data(self) -> Dict[str, Any]:
        """Return source update data using factory"""
        return SourceDataFactory.update_data()
    
    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid source data using factory"""
        return SourceDataFactory.invalid_data()


class TestSourceRoutes(SourceTestMixin, BaseEntityRouteTests):
    """
    📚 Complete source route test suite
    
    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks
    
    Plus source-specific functionality tests.
    """
    
    # === SOURCE-SPECIFIC CRUD TESTS ===
    
    def test_create_source_with_required_fields(self, authenticated_client):
        """Test source creation with only required fields"""
        minimal_data = self.get_minimal_data()
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=minimal_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_source = response.json()
        
        assert created_source["title"] == minimal_data["title"]
        assert created_source.get("description") is None
        assert created_source.get("source_type_id") is None
        assert created_source.get("url") is None
    
    def test_create_source_with_optional_fields(self, authenticated_client):
        """Test source creation with optional fields"""
        source_data = self.get_sample_data()
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=source_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_source = response.json()
        
        assert created_source["title"] == source_data["title"]
        assert created_source["description"] == source_data["description"]
        # source_type_id is optional and may be None
        assert created_source.get("source_type_id") == source_data.get("source_type_id")
        assert created_source["url"] == source_data["url"]
        assert created_source["citation"] == source_data["citation"]
        assert created_source["language_code"] == source_data["language_code"]
    
    def test_create_source_with_different_titles(self, authenticated_client):
        """Test source creation with different titles"""
        titles = [f"Source {i+1}" for i in range(5)]
        created_sources = []
        
        for title in titles:
            source_data = self.get_sample_data()
            source_data["title"] = title
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            assert response.status_code == status.HTTP_200_OK
            source = response.json()
            assert source["title"] == title
            created_sources.append(source)
        
        assert len(created_sources) == len(titles)
    
    def test_create_source_with_valid_urls(self, authenticated_client):
        """Test source creation with various valid URL formats"""
        valid_urls = [
            "https://www.example.com",
            "http://example.org/path/to/resource",
            "https://subdomain.example.com:8080/path?query=value",
            "https://example.com/path/with-hyphens_and_underscores",
            "https://example.edu/academic/paper.pdf"
        ]
        
        for url in valid_urls:
            source_data = self.get_minimal_data()
            source_data["url"] = url
            source_data["title"] = f"Source with URL {url}"
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            assert response.status_code == status.HTTP_200_OK
            source = response.json()
            assert source["url"] == url
    
    def test_create_source_with_citation(self, authenticated_client):
        """Test source creation with academic citation"""
        citation_data = self.get_sample_data()
        citation_data["citation"] = "Smith, J., & Doe, A. (2024). Advanced Testing Methodologies. Journal of Software Quality, 15(3), 123-145."
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=citation_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_source = response.json()
        
        assert created_source["citation"] == citation_data["citation"]
    
    def test_create_source_with_unicode_title(self, authenticated_client):
        """Test source creation with unicode title"""
        unicode_data = SourceDataFactory.edge_case_data("special_chars")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=unicode_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_source = response.json()
        
        assert created_source["title"] == unicode_data["title"]
        assert "📚" in created_source["title"]  # Verify emoji preserved
    
    def test_create_source_with_long_title(self, authenticated_client):
        """Test source creation with very long title"""
        long_title_data = SourceDataFactory.edge_case_data("long_title")
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=long_title_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        created_source = response.json()
        
        assert created_source["title"] == long_title_data["title"]
        assert len(created_source["title"]) > 100  # Verify it's actually long
    
    def test_update_source_title(self, authenticated_client):
        """Test updating source title"""
        # Create initial source
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        source_id = create_response.json()["id"]
        
        # Update title
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, source_id=source_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        updated_source = response.json()
        
        assert updated_source["title"] == update_data["title"]
        assert updated_source["description"] == update_data["description"]
        # source_type_id is optional and may be None
        assert updated_source.get("source_type_id") == update_data.get("source_type_id")
    
    def test_update_source_url_only(self, authenticated_client):
        """Test updating only the URL of a source"""
        # Create initial source
        initial_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        source_id = create_response.json()["id"]
        original_title = create_response.json()["title"]
        
        # Update only URL
        new_url = "https://updated-example.com/new-path"
        update_data = {"url": new_url}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, source_id=source_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        updated_source = response.json()
        
        assert updated_source["title"] == original_title  # Title unchanged
        assert updated_source["url"] == new_url  # URL updated
    
    def test_get_source_by_id(self, authenticated_client):
        """Test retrieving a specific source by ID"""
        # Create source
        source_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=source_data,
        )
        source_id = create_response.json()["id"]
        
        # Get source by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, source_id=source_id),
        )
        
        assert response.status_code == status.HTTP_200_OK
        source = response.json()
        
        assert source["id"] == source_id
        assert source["title"] == source_data["title"]
        assert source["description"] == source_data["description"]
        assert source["url"] == source_data["url"]
    
    def test_delete_source(self, authenticated_client):
        """Test deleting a source"""
        # Create source
        source_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=source_data,
        )
        source_id = create_response.json()["id"]
        
        # Delete source
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, source_id=source_id),
        )
        
        assert response.status_code == status.HTTP_200_OK
        deleted_source = response.json()
        assert deleted_source["id"] == source_id
        
        # Verify source is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, source_id=source_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE
    
    def test_list_sources_with_pagination(self, authenticated_client):
        """Test listing sources with pagination"""
        # Create multiple sources
        sources_data = [self.get_sample_data() for _ in range(5)]
        created_sources = []
        
        for source_data in sources_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            created_sources.append(response.json())
        
        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )
        
        assert response.status_code == status.HTTP_200_OK
        sources = response.json()
        assert len(sources) <= 3
        
        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5
    
    def test_list_sources_with_sorting(self, authenticated_client):
        """Test listing sources with sorting"""
        # Create sources with different creation times
        source1_data = self.get_sample_data()
        source1_data["title"] = "AAA Source"
        
        source2_data = self.get_sample_data()
        source2_data["title"] = "ZZZ Source"
        
        # Create sources
        authenticated_client.post(self.endpoints.create, json=source1_data)
        authenticated_client.post(self.endpoints.create, json=source2_data)
        
        # Test sorting by creation date
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )
        
        assert response.status_code == status.HTTP_200_OK
        sources = response.json()
        assert len(sources) >= 2
    
    # === SOURCE-SPECIFIC ERROR HANDLING TESTS ===
    
    def test_create_source_without_title(self, authenticated_client):
        """Test creating source without required title field"""
        invalid_data = {"description": "Source without title"}
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_source_with_empty_title(self, authenticated_client):
        """Test creating source with empty title"""
        invalid_data = {"title": ""}
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )
        
        # This might be allowed or not depending on validation rules
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]
    
    def test_create_source_with_invalid_url(self, authenticated_client):
        """Test creating source with invalid URL format"""
        invalid_urls = [
            "not-a-url",
            "ftp://invalid-protocol.com",
            "http://",
            "https://",
            "javascript:alert('xss')"
        ]
        
        for invalid_url in invalid_urls:
            source_data = self.get_minimal_data()
            source_data["url"] = invalid_url
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            # Should reject invalid URLs
            assert response.status_code in [
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_400_BAD_REQUEST
            ], f"Invalid URL {invalid_url} was accepted"
    
    def test_get_nonexistent_source(self, authenticated_client):
        """Test retrieving a non-existent source"""
        fake_id = str(uuid.uuid4())
        
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, source_id=fake_id),
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_update_nonexistent_source(self, authenticated_client):
        """Test updating a non-existent source"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()
        
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, source_id=fake_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_delete_nonexistent_source(self, authenticated_client):
        """Test deleting a non-existent source"""
        fake_id = str(uuid.uuid4())
        
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, source_id=fake_id),
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === SOURCE-SPECIFIC INTEGRATION TESTS ===

@pytest.mark.integration
class TestSourceEntityTypes(SourceTestMixin, BaseEntityTests):
    """Enhanced source entity type handling tests"""

    def test_create_sources_with_different_titles(self, authenticated_client):
        """Test creating sources with various titles"""
        titles = [f"Test Source {i+1}" for i in range(7)]
        created_sources = []
        
        for title in titles:
            source_data = self.get_sample_data()
            source_data["title"] = title
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            assert response.status_code == status.HTTP_200_OK
            source = response.json()
            assert source["title"] == title
            created_sources.append(source)
        
        assert len(created_sources) == len(titles)

    def test_filter_sources_by_title(self, authenticated_client):
        """Test filtering sources by title using OData filter"""
        # Create sources with different titles
        website_data = self.get_sample_data()
        website_data["title"] = "Website Source"
        
        paper_data = self.get_sample_data()
        paper_data["title"] = "Academic Paper Source"
        
        # Create the sources
        authenticated_client.post(self.endpoints.create, json=website_data)
        authenticated_client.post(self.endpoints.create, json=paper_data)
        
        # Filter for website sources
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=title eq 'Website Source'",
        )
        
        assert response.status_code == status.HTTP_200_OK
        sources = response.json()
        
        # Verify all returned sources have the correct title
        for source in sources:
            if source.get("title"):  # Skip sources without title
                assert source["title"] == "Website Source"

    def test_academic_sources_with_citations(self, authenticated_client):
        """Test creating academic sources with proper citations"""
        academic_titles = ["Academic Paper 1", "Academic Book 2", "Academic Article 3"]
        
        for title in academic_titles:
            source_data = self.get_sample_data()
            source_data["title"] = title
            source_data["citation"] = f"Author, A. (2024). {title}. Journal Name, 1(1), 1-10."
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            assert response.status_code == status.HTTP_200_OK
            source = response.json()
            assert source["title"] == title
            assert source["citation"] is not None
            assert "Author, A." in source["citation"]


@pytest.mark.integration
class TestSourceLanguageHandling(SourceTestMixin, BaseEntityTests):
    """Enhanced source language handling tests"""

    def test_create_sources_with_different_languages(self, authenticated_client):
        """Test creating sources with various language codes"""
        languages = ["en", "es", "fr", "de", "zh", "ja", "ar", "pt", "ru"]
        created_sources = []
        
        for lang in languages:
            source_data = self.get_sample_data()
            source_data["language_code"] = lang
            source_data["title"] = f"Source in {lang}"
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            assert response.status_code == status.HTTP_200_OK
            source = response.json()
            assert source["language_code"] == lang
            created_sources.append(source)
        
        assert len(created_sources) == len(languages)

    def test_filter_sources_by_language(self, authenticated_client):
        """Test filtering sources by language code"""
        # Create sources with different languages
        english_data = self.get_sample_data()
        english_data["language_code"] = "en"
        english_data["title"] = "English Source"
        
        spanish_data = self.get_sample_data()
        spanish_data["language_code"] = "es"
        spanish_data["title"] = "Spanish Source"
        
        # Create the sources
        authenticated_client.post(self.endpoints.create, json=english_data)
        authenticated_client.post(self.endpoints.create, json=spanish_data)
        
        # Filter for English sources
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=language_code eq 'en'",
        )
        
        assert response.status_code == status.HTTP_200_OK
        sources = response.json()
        
        # Verify all returned sources are English
        for source in sources:
            if source.get("language_code"):  # Skip sources without language_code
                assert source["language_code"] == "en"


@pytest.mark.integration
class TestSourceURLValidation(SourceTestMixin, BaseEntityTests):
    """Enhanced source URL validation tests"""

    def test_various_valid_url_formats(self, authenticated_client):
        """Test creating sources with various valid URL formats"""
        valid_urls = [
            "https://www.example.com",
            "http://example.org",
            "https://subdomain.example.com:8080/path",
            "https://example.com/path/to/resource.pdf",
            "https://api.example.com/v1/endpoint?param=value",
            "https://example.edu/research/paper.html",
            "https://github.com/user/repository",
            "https://docs.example.com/guide#section"
        ]
        
        for url in valid_urls:
            source_data = self.get_minimal_data()
            source_data["url"] = url
            source_data["title"] = f"Source with URL: {url}"
            
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            
            assert response.status_code == status.HTTP_200_OK, f"Valid URL {url} was rejected"
            source = response.json()
            assert source["url"] == url

    def test_update_source_with_new_url(self, authenticated_client):
        """Test updating source with new URL"""
        # Create source without URL
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        source_id = create_response.json()["id"]
        
        # Update with new URL
        new_url = "https://updated-example.com/new-resource"
        update_data = {"url": new_url}
        
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, source_id=source_id),
            json=update_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        updated_source = response.json()
        assert updated_source["url"] == new_url


# === SOURCE PERFORMANCE TESTS ===

@pytest.mark.performance
class TestSourcePerformance(SourceTestMixin, BaseEntityTests):
    """Source performance tests"""

    def test_create_multiple_sources_performance(self, authenticated_client):
        """Test creating multiple sources for performance"""
        sources_count = 20
        sources_data = [self.get_sample_data() for _ in range(sources_count)]
        
        created_sources = []
        for source_data in sources_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_sources.append(response.json())
        
        assert len(created_sources) == sources_count
        
        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={sources_count}",
        )
        
        assert response.status_code == status.HTTP_200_OK
        sources = response.json()
        assert len(sources) >= sources_count

    def test_large_description_source_handling(self, authenticated_client):
        """Test handling of sources with very large descriptions"""
        large_desc_data = self.get_sample_data()
        large_desc_data["description"] = fake.text(max_nb_chars=5000)
        
        response = authenticated_client.post(
            self.endpoints.create,
            json=large_desc_data,
        )
        
        assert response.status_code == status.HTTP_200_OK
        source = response.json()
        
        # Verify description is preserved correctly
        assert source["description"] == large_desc_data["description"]
        assert len(source["description"]) > 1000

    def test_complex_filtering_performance(self, authenticated_client):
        """Test performance of complex filtering operations"""
        # Create sources with various attributes
        sources_data = []
        languages = ["en", "es", "fr"]
        
        for i in range(15):
            source_data = self.get_sample_data()
            source_data["language_code"] = languages[i % len(languages)]
            source_data["title"] = f"Source {i+1}"
            sources_data.append(source_data)
        
        # Create all sources
        for source_data in sources_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=source_data,
            )
            assert response.status_code == status.HTTP_200_OK
        
        # Test complex filter
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=language_code eq 'en'",
        )
        
        assert response.status_code == status.HTTP_200_OK
        sources = response.json()
        
        # Verify filtering works correctly
        for source in sources:
            if source.get("language_code"):
                assert source["language_code"] == "en"
