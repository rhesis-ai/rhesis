# Import base classes first
# Import remaining models
from .activity_log import ActivityLog
from .architect import ArchitectMessage, ArchitectSession
from .base import Base
from .category import Category
from .chunk import Chunk
from .comment import Comment
from .embedding import Embedding
from .endpoint import Endpoint
from .execution_trace import ExecutionTrace
from .experiment import Experiment
from .file import File
from .guid import GUID
from .job import Job
from .metric import Metric, behavior_metric_association, requirement_metric_association
from .mixins import ProjectMixin, TagsMixin
from .model import Model
from .notification import Notification
from .organization import Organization

# Import models with dependencies
from .project import Project
from .project_membership import ProjectMembership
from .prompt import Prompt
from .prompt_template import PromptTemplate
from .refresh_token import RefreshToken
from .requirement import Requirement
from .source import Source

# Import stats view models
from .stats_views import MetricStatsView, TestResultStatsView, TestRunStatsView

# Import models without dependencies first
from .status import Status
from .subscription import Subscription, SubscriptionPlan
from .tag import Tag, TaggedItem
from .task import Task
from .test import Test, test_test_set_association
from .test_configuration import TestConfiguration
from .test_result import TestResult
from .test_run import TestRun
from .test_set import TestSet, test_set_metric_association
from .token import Token
from .tool import Tool
from .topic import Topic
from .trace import Trace
from .type_lookup import TypeLookup
from .usage import Usage
from .user import User

# Frozen migration b857edcac3c0 references models.Behavior by name.
Behavior = Requirement

# This line ensures all models are registered with Base
__all__ = [
    "Base",
    "ActivityLog",
    "ArchitectSession",
    "ArchitectMessage",
    "Behavior",
    "Requirement",
    "TestSet",
    "Category",
    "Chunk",
    "Comment",
    "Embedding",
    "Endpoint",
    "Experiment",
    "File",
    "GUID",
    "Job",
    "Metric",
    "Model",
    "Notification",
    "PromptTemplate",
    "Prompt",
    "TestConfiguration",
    "TestResult",
    "TestSet",
    "User",
    "Subscription",
    "SubscriptionPlan",
    "Status",
    "Source",
    "Topic",
    "TestRun",
    "TypeLookup",
    "Tag",
    "TaggedItem",
    "TagsMixin",
    "ProjectMixin",
    "Token",
    "RefreshToken",
    "Organization",
    "Project",
    "ProjectMembership",
    "Task",
    "Test",
    "Tool",
    "Trace",
    "behavior_metric_association",
    "requirement_metric_association",
    "test_test_set_association",
    "test_set_metric_association",
    "TestRunStatsView",
    "TestResultStatsView",
    "MetricStatsView",
    "Usage",
]

# Set up soft delete event listener
from .soft_delete_events import setup_soft_delete_listener

setup_soft_delete_listener()

# Set up ambient scope event listeners (auto-filter + auto-stamp)
from .scope_events import setup_scope_listeners

setup_scope_listeners()
