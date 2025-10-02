"""
🗄️ CRUD Operations Test Package

Domain-specific CRUD operation tests organized by application structure.
Each test file focuses on a specific domain's CRUD operations while ensuring
proper tenant isolation and data integrity.

Test Structure:
- test_tag_crud.py: Tag assignment and removal operations
- test_token_crud.py: Token management operations
- test_test_crud.py: Test entity operations
- test_metric_crud.py: Metric operations and behavior associations
- test_behavior_metric_crud.py: Cross-domain behavior-metric operations

Run all CRUD tests with: python -m pytest tests/backend/crud/ -v
"""
