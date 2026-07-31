from fastapi import APIRouter, Depends

from app.dependencies import get_classification_service
from app.models.classification import CpcClassificationRequest, CpcClassificationResponse
from app.services.classification_service import ClassificationService

router = APIRouter(prefix="/clasificacion", tags=["clasificacion"])


@router.post("/cpc/recommend", response_model=CpcClassificationResponse)
def recommend_cpc(
    request: CpcClassificationRequest,
    service: ClassificationService = Depends(get_classification_service),
) -> CpcClassificationResponse:
    return service.recommend(request.description, request.top_k)
