"""
🧪 Base Route Test Classes - Backward Compatibility

This file maintains backward compatibility by re-exporting all the modular
base test classes. The actual implementation has been moved to the `test_base/`
package for better organization and maintainability.

For new development, consider importing directly from the test_base package:
    from tests.backend.routes.test_base import BaseEntityRouteTests

This file will continue to work for existing imports:
    from tests.backend.routes.base import BaseEntityRouteTests
"""

# Re-export everything from the modular test_base package for backward compatibility
from .test_base import *
