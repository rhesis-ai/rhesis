# Import existing routers
from .auth import router as auth_router
from .behavior import router as behavior_router
from .category import router as category_router
from .comment import router as comment_router
from .connector import router as connector_router
from .demographic import router as demographic_router
from .dimension import router as dimension_router
from .endpoint import router as endpoint_router
from .garak import router as garak_router
from .home import router as home_router

# ... other imports
# Import new routers
from .job import router as task_router
from .metric import router as metric_router
from .model import router as model_router
from .organization import router as organization_router
from .project import router as project_router
from .prompt import router as prompt_router
from .prompt_template import router as prompt_template_router
from .recycle import router as recycle_router
from .response_pattern import router as response_pattern_router
from .risk import router as risk_router
from .services import router as services_router
from .source import router as source_router
from .status import router as status_router
from .tag import router as tag_router
from .task_management import router as task_management_router
from .telemetry import router as telemetry_router
from .test import router as test_router
from .test_configuration import router as test_configuration_router
from .test_context import router as test_context_router
from .test_result import router as test_result_router
from .test_run import router as test_run_router
from .test_set import router as test_set_router
from .token import router as token_router
from .tools import router as tools_router
from .topic import router as topic_router
from .type_lookup import router as type_lookup_router
from .use_case import router as use_case_router
from .user import router as user_router
from .websocket import router as websocket_router

# Export all modules for explicit imports
__all__ = [
    "endpoint",
    "use_case",
    "prompt",
    "prompt_template",
    "category",
    "behavior",
    "comment",
    "connector",
    "response_pattern",
    "test_set",
    "test_configuration",
    "test_result",
    "status",
    "risk",
    "topic",
    "user",
    "demographic",
    "dimension",
    "test_run",
    "tag",
    "auth",
    "token",
    "home",
    "services",
    "organization",
    "project",
    "type_lookup",
    "test",
    "test_context",
    "metric",
    "model",
    "task",
    "task_management",
    "garak",
]

# Export all routers for use in main.py
routers = sorted(
    [
        endpoint_router,
        use_case_router,
        prompt_router,
        prompt_template_router,
        category_router,
        behavior_router,
        comment_router,
        connector_router,
        telemetry_router,
        response_pattern_router,
        test_set_router,
        test_configuration_router,
        test_result_router,
        source_router,
        status_router,
        risk_router,
        topic_router,
        user_router,
        demographic_router,
        dimension_router,
        test_run_router,
        tag_router,
        auth_router,
        token_router,
        home_router,
        services_router,
        organization_router,
        project_router,
        test_router,
        test_context_router,
        type_lookup_router,
        metric_router,
        model_router,
        task_router,
        task_management_router,
        tools_router,
        recycle_router,
        garak_router,
        websocket_router,
    ],
    key=lambda x: x.tags[0].lower() if x.tags else "",
)
