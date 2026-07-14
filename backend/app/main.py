from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.patents import router as patents_router
from app.routes.chat import router as chat_router

app = FastAPI(title="Patentologos API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patents_router)
app.include_router(chat_router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "patentologos-api"}
