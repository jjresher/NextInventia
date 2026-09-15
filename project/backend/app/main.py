from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.chat import router as chat_router
from app.routes.classification import router as classification_router
from app.routes.patents import router as patents_router

LOCAL_NETWORK_ORIGIN_REGEX = (
    r"^http://(?:localhost|127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d+)?$"
)

app = FastAPI(title="Patentologos API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_origin_regex=(
        LOCAL_NETWORK_ORIGIN_REGEX if settings.allow_local_network_origins else None
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patents_router)
app.include_router(chat_router)
app.include_router(classification_router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "patentologos-api"}
