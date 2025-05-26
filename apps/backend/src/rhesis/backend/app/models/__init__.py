# Import base classes first
from .base import Base

# Import remaining models
from .behavior import Behavior
from .category import Category
from .demographic import Demographic
from .dimension import Dimension
from .endpoint import Endpoint
from .guid import GUID
from .metric import Metric, behavior_metric_association
from .mixins import TagsMixin
from .model import Model
from .organization import Organization

# Import models with dependencies
from .project import Project
from .prompt import Prompt
from .prompt_template import PromptTemplate
from .response_pattern import ResponsePattern
from .risk import Risk
from .source import Source

# Import models without dependencies first
from .status import Status
from .subscription import Subscription, SubscriptionPlan
from .tag import Tag, TaggedItem
from .test import Test
from .test_configuration import TestConfiguration
from .test_context import TestContext
from .test_result import TestResult
from .test_run import TestRun
from .test_set import TestSet
from .token import Token
from .topic import Topic
from .type_lookup import TypeLookup
from .use_case import UseCase
from .user import User

# This line ensures all models are registered with Base
__all__ = [
    "Base",
    "Behavior",
    "TestSet",
    "Category",
    "Endpoint",
    "GUID",
    "Metric",
    "Model",
    "PromptTemplate",
    "Prompt",
    "ResponsePattern",
    "TestConfiguration",
    "TestResult",
    "UseCase",
    "TestSet",
    "Risk",
    "User",
    "Subscription",
    "SubscriptionPlan",
    "Status",
    "Source",
    "Topic",
    "Demographic",
    "Dimension",
    "TestRun",
    "TypeLookup",
    "Tag",
    "TaggedItem",
    "TagsMixin",
    "Token",
    "Organization",
    "Project",
    "Test",
    "TestContext",
    "behavior_metric_association",
]
