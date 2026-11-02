"""Turn an annotated exchange into a metric tuning case.

The case copies the input and output the annotation judged. Like every tuning case
it carries no expected verdict (see ``metric_tuning.cases``): the reviewer judges
what the metric says about it after a run. The new case is remembered on the
annotation's ``attributes["tuning_cases"]``.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.annotation import add_tuning_case_reference, get_annotation
from rhesis.backend.app.crud.metric import get_metric
from rhesis.backend.app.schemas.annotation import AnnotationTuningCase, AnnotationTuningCaseCreate
from rhesis.backend.app.schemas.metric_tuning import MetricTuningCaseCreate
from rhesis.backend.app.services import metric_tuning
from rhesis.backend.app.services.annotation_exchange import exchanges_for


def _tunable_metric(
    db: Session, metric_id: uuid.UUID, organization_id: str, user_id: str
) -> models.Metric:
    metric = get_metric(db, metric_id=metric_id, organization_id=organization_id, user_id=user_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    if not metric_tuning.is_tunable(metric):
        raise HTTPException(status_code=400, detail="Only custom metrics can be tuned.")
    return metric


def create_tuning_case_from_annotation(
    db: Session,
    annotation_id: uuid.UUID,
    body: AnnotationTuningCaseCreate,
    organization_id: str,
    user_id: str,
) -> AnnotationTuningCase:
    annotation = get_annotation(db, annotation_id, organization_id, user_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    metric = _tunable_metric(db, body.metric_id, organization_id, user_id)

    input_text, output_text = exchanges_for(db, [annotation])[annotation.id]
    if not input_text or not output_text:
        raise HTTPException(
            status_code=400,
            detail="This annotation has no input and output to copy into a tuning case.",
        )

    try:
        case = metric_tuning.create_tuning_case(
            db,
            metric,
            MetricTuningCaseCreate(input=input_text, output=output_text),
            organization_id,
            user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    add_tuning_case_reference(db, annotation, metric.id, case.id)
    db.commit()
    return AnnotationTuningCase(metric_id=metric.id, case_id=case.id)
