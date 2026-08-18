# Import existing routers
from .annotations import router as annotations_router
from .architect import router as architect_router
from .auth import router as auth_router
from .requirement import router as requirement_router
from .capabilities import router as capabilities_router
from .category import router as category_router
from .comment import router as comment_router
from .connector import router as connector_router
from .endpoint import router as endpoint_router
from .experiments import router as experiments_router
from .explorer import router as explorer_router
from .features import router as features_router
from .feedback import router as feedback_router
from .file import router as file_router
from .file_import import router as file_import_router
from .garak import router as garak_router
from .home import router as home_router
from .insights import router as insights_router

# ... other imports
# Import new routers
from .job import router as task_router
from .metric import router as metric_router
from .model import router as model_router
from .notification import router as notification_router
from .organization import router as organization_router
from .owasp import router as owasp_router
from .parameters import (
    project_experiments_router as project_experiments_router,
)
from .parameters import (
    router as parameters_router,
)
from .platform import router as platform_router
from .preflight import router as preflight_router
from .project import router as project_router
from .prompt import router as prompt_router
from .prompt_template import router as prompt_template_router
from .recycle import router as recycle_router
from .resolve import router as resolve_router
from .services import router as services_router
from .source import router as source_router

# EE-feature routers are not imported here; they are registered by
# ``rhesis.backend.app.ee_bootstrap.bootstrap_ee`` from the optional
# ``rhesis-backend-ee`` package.
from .status import router as status_router
from .tag import router as tag_router
from .task_management import router as task_management_router
from .telemetry import router as telemetry_router
from .test import router as test_router
from .test_configuration import router as test_configuration_router
from .test_result import router as test_result_router
from .test_run import router as test_run_router
from .test_set import router as test_set_router
from .token import router as token_router
from .tools import router as tools_router
from .topic import router as topic_router
from .type_lookup import router as type_lookup_router
from .usage import router as usage_router
from .user import router as user_router
from .websocket import router as websocket_router

# Export all modules for explicit imports
__all__ = [
    "annotations",
    "endpoint",
    "prompt",
    "prompt_template",
    "category",
    "requirement",
    "comment",
    "connector",
    "test_set",
    "test_configuration",
    "test_result",
    "status",
    "topic",
    "user",
    "test_run",
    "tag",
    "auth",
    "token",
    "home",
    "services",
    "organization",
    "parameters",
    "experiments",
    "project",
    "type_lookup",
    "test",
    "metric",
    "model",
    "task",
    "task_management",
    "garak",
    "owasp",
    "capabilities",
    "features",
    "file",
    "file_import",
    "explorer",
    "architect",
    "preflight",
    "usage",
    "platform",
]

# Export all routers for use in main.py
routers = sorted(
    [
        annotations_router,
        endpoint_router,
        prompt_router,
        prompt_template_router,
        category_router,
        requirement_router,
        comment_router,
        connector_router,
        telemetry_router,
        test_set_router,
        test_configuration_router,
        test_result_router,
        source_router,
        status_router,
        topic_router,
        user_router,
        test_run_router,
        tag_router,
        auth_router,
        token_router,
        home_router,
        insights_router,
        services_router,
        organization_router,
        preflight_router,
        parameters_router,
        project_experiments_router,
        experiments_router,
        project_router,
        test_router,
        type_lookup_router,
        metric_router,
        model_router,
        notification_router,
        task_router,
        task_management_router,
        tools_router,
        recycle_router,
        resolve_router,
        garak_router,
        owasp_router,
        features_router,
        feedback_router,
        file_router,
        file_import_router,
        websocket_router,
        explorer_router,
        architect_router,
        capabilities_router,
        usage_router,
        platform_router,
    ],
    key=lambda x: x.tags[0].lower() if x.tags else "",
)
