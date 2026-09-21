"""Azure DevOps organization-name normalization.

Used as the ``normalize`` hook on the manifest's ``AZURE_DEVOPS_ORG`` field,
so a user can paste a ``dev.azure.com/org`` URL where an org name is asked for.
"""

import re

_AZURE_DEVOPS_ORG_NAME = re.compile(r"^[\w][\w.-]*$")


def normalize_azure_devops_org(value: str) -> str:
    """Extract an organization name from common Azure DevOps URL shapes."""
    trimmed = value.strip().rstrip("/")
    if not trimmed:
        raise ValueError("Azure DevOps 'AZURE_DEVOPS_ORG' must be a non-empty string")

    dev_azure = re.search(r"dev\.azure\.com/([^/?#]+)", trimmed, re.IGNORECASE)
    if dev_azure:
        trimmed = dev_azure.group(1)

    visualstudio = re.search(
        r"(?:https?://)?([\w-]+)\.visualstudio\.com",
        trimmed,
        re.IGNORECASE,
    )
    if visualstudio:
        trimmed = visualstudio.group(1)

    if "://" in trimmed or trimmed.lower().startswith("http"):
        raise ValueError("Azure DevOps 'AZURE_DEVOPS_ORG' must be the organization name, not a URL")

    if "/" in trimmed:
        raise ValueError("Azure DevOps 'AZURE_DEVOPS_ORG' must be a single organization name")

    if re.search(r"dev\.azure\.com|visualstudio\.com", trimmed, re.IGNORECASE):
        raise ValueError("Azure DevOps 'AZURE_DEVOPS_ORG' must be the organization name, not a URL")

    if not _AZURE_DEVOPS_ORG_NAME.match(trimmed):
        raise ValueError("Azure DevOps 'AZURE_DEVOPS_ORG' contains invalid characters")

    return trimmed
