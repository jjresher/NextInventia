from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_classification_service
from app.models.classification import CpcClassificationRequest, CpcClassificationResponse
from app.services.classification_service import ClassificationService, CpcIndexError

router = APIRouter(prefix="/clasificacion", tags=["clasificacion"])


@router.post("/cpc/recommend", response_model=CpcClassificationResponse)
def recommend_cpc(
    request: CpcClassificationRequest,
    service: ClassificationService = Depends(get_classification_service),
) -> CpcClassificationResponse:
    try:
        return service.recommend(request.description, request.top_k)
    except CpcIndexError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
