from .base import BaseSourceHandler
from .document import DocumentHandler

# Registry mapping source type values to handler classes
HANDLER_REGISTRY = {
    "Document": DocumentHandler,
    # Future handlers can be added here:
    # "Website": WebsiteHandler,
    # "API": APIHandler,
    # "Notion": NotionHandler,
}


def get_source_handler(source_type: str, **kwargs) -> BaseSourceHandler:
    """Create a source handler instance based on the source type.

    This function provides a factory pattern for creating source handlers,
    similar to the SDK's model factory. Each source type has its own
    specialized handler implementation.

    Args:
        source_type: The type of source (e.g., "Document", "Website", "API")
        **kwargs: Additional parameters passed to the handler constructor

    Returns:
        BaseSourceHandler: Configured handler instance

    Raises:
        ValueError: If source type is not supported

    Examples:
        >>> # Create a document handler
        >>> handler = get_source_handler("Document")

        >>> # Create with custom parameters
        >>> handler = get_source_handler("Document", max_size=10*1024*1024)
    """
    handler_class = HANDLER_REGISTRY.get(source_type)
    if handler_class is None:
        available_types = list(HANDLER_REGISTRY.keys())
        raise ValueError(
            f"Source type '{source_type}' not supported. Available types: {available_types}"
        )
    return handler_class(**kwargs)


def get_available_source_types() -> list[str]:
    """Get list of all available source types.

    Returns:
        list[str]: List of available source type values
    """
    return list(HANDLER_REGISTRY.keys())
