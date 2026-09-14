from fastapi import Depends, Request
from supabase import Client

from app.services.classification_service import ClassificationService
from app.services.gemini_client import GeminiFallbackClient
from app.services.patent_service import PatentService


def get_supabase(request: Request) -> Client:
    return request.app.state.supabase


def get_patent_service(client: Client = Depends(get_supabase)) -> PatentService:
    return PatentService(client)


def get_gemini_client(request: Request) -> GeminiFallbackClient:
    return request.app.state.gemini


def get_classification_service(request: Request) -> ClassificationService:
    return request.app.state.classification_service
