from fastapi import Depends
from supabase import Client, create_client

from app.config import settings
from app.services.classification_service import ClassificationService
from app.services.patent_service import PatentService

_classification_service: ClassificationService | None = None


def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)


def get_patent_service(client: Client = Depends(get_supabase)) -> PatentService:
    return PatentService(client)


def get_classification_service() -> ClassificationService:
    global _classification_service
    if _classification_service is None:
        _classification_service = ClassificationService()
    return _classification_service
