from fastapi import Depends
from supabase import Client, create_client

from app.config import settings
from app.services.patent_service import PatentService


def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)


def get_patent_service(client: Client = Depends(get_supabase)) -> PatentService:
    return PatentService(client)
