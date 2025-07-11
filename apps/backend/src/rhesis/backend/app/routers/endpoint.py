import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.app.services.endpoint import EndpointService
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Use rhesis logger
from rhesis.backend.logging import logger

# Create the detailed schema for Endpoint
EndpointDetailSchema = create_detailed_schema(schemas.Endpoint, models.Endpoint)


router = APIRouter(
    prefix="/endpoints",
    tags=["endpoints"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Endpoint)
def create_endpoint(endpoint: schemas.EndpointCreate, db: Session = Depends(get_db)):
    return crud.create_endpoint(db=db, endpoint=endpoint)


@router.get("/", response_model=list[EndpointDetailSchema])
@with_count_header(model=models.Endpoint)
def read_endpoints(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
):
    """Get all endpoints with their related objects"""
    return crud.get_endpoints(
        db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
    )


@router.get("/{endpoint_id}", response_model=EndpointDetailSchema)
def read_endpoint(endpoint_id: uuid.UUID, db: Session = Depends(get_db)):
    db_endpoint = crud.get_endpoint(db, endpoint_id=endpoint_id)
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return db_endpoint


@router.delete("/{endpoint_id}", response_model=schemas.Endpoint)
def delete_endpoint(endpoint_id: uuid.UUID, db: Session = Depends(get_db)):
    db_endpoint = crud.delete_endpoint(db, endpoint_id=endpoint_id)
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return db_endpoint


@router.put("/{endpoint_id}", response_model=schemas.Endpoint)
def update_endpoint(
    endpoint_id: uuid.UUID,
    endpoint: schemas.EndpointUpdate,
    db: Session = Depends(get_db),
):
    db_endpoint = crud.update_endpoint(db, endpoint_id=endpoint_id, endpoint=endpoint)
    if db_endpoint is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return db_endpoint


@router.post("/{endpoint_id}/invoke")
def invoke_endpoint(
    endpoint_id: uuid.UUID,
    input_data: Dict[str, Any],
    db: Session = Depends(get_db),
    endpoint_service: EndpointService = Depends(get_endpoint_service)
):
    """
    Invoke an endpoint with the given input data.

    Args:
        endpoint_id: The UUID of the endpoint to invoke
        input_data: Dictionary containing input data for the endpoint
        db: Database session
        endpoint_service: The endpoint service instance

    Returns:
        The response from the endpoint, either mapped or raw depending on endpoint configuration
    """
    try:
        logger.info(f"API invoke request for endpoint {endpoint_id} with input: {input_data}")
        
        # Validate that input_data contains required fields
        if not isinstance(input_data, dict):
            raise HTTPException(
                status_code=400, 
                detail="Input data must be a JSON object"
            )
        
        # If input_data doesn't have 'input' field, provide helpful error
        if 'input' not in input_data:
            logger.warning(f"Input data missing 'input' field. Received keys: {list(input_data.keys())}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required field 'input'",
                    "received_fields": list(input_data.keys()),
                    "expected_format": {
                        "input": "Your query text here",
                        "session_id": "optional-session-id"
                    }
                }
            )
        
        result = endpoint_service.invoke_endpoint(db, str(endpoint_id), input_data)
        logger.info(f"API invoke successful for endpoint {endpoint_id}")
        return result
    except HTTPException as e:
        logger.error(f"API invoke HTTPException for endpoint {endpoint_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"API invoke unexpected error for endpoint {endpoint_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
def get_endpoint_schema(endpoint_service: EndpointService = Depends(get_endpoint_service)):
    """
    Get the endpoint schema definition.

    Args:
        endpoint_service: The endpoint service instance

    Returns:
        Dict containing the input and output schema definitions
    """
    return endpoint_service.get_schema()
