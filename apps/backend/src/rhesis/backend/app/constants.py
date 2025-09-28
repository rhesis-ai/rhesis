from enum import Enum


# Entity Types Enum - Unified for all entities including comments
class EntityType(Enum):
    GENERAL = "General"
    TEST = "Test"
    TEST_SET = "TestSet"
    TEST_RUN = "TestRun"
    TEST_RESULT = "TestResult"
    METRIC = "Metric"
    MODEL = "Model"
    PROMPT = "Prompt"
    BEHAVIOR = "Behavior"
    CATEGORY = "Category"
    TOPIC = "Topic"
    DIMENSION = "Dimension"
    DEMOGRAPHIC = "Demographic"
    TASK = "Task"
    PROJECT = "Project"

    @classmethod
    def get_value(cls, entity_type):
        """Get the string value of an entity type"""
        if isinstance(entity_type, cls):
            return entity_type.value
        return entity_type


# Error messages
ERROR_INVALID_UUID = "Invalid UUID format in input parameters: {error}"
ERROR_TEST_SET_NOT_FOUND = "Test set with ID {test_set_id} not found"
ERROR_ENTITY_NOT_FOUND = "{entity} with ID {entity_id} not found"
ERROR_BULK_CREATE_FAILED = "Failed to create {entity}: {error}"
ERROR_ASSOCIATION_FAILED = "An error occurred while creating test set associations: {error}"
ERROR_DISASSOCIATION_FAILED = "Failed to remove test set associations: {error}"

# Success messages
SUCCESS_ASSOCIATIONS_CREATED = "Successfully associated {count} new test{plural}"
SUCCESS_ASSOCIATIONS_REMOVED = "Successfully removed {count} test associations"

# Default values
DEFAULT_BATCH_SIZE = 100
DEFAULT_PRIORITY = 1
