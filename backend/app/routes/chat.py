import logging
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_client = genai.Client(api_key=settings.gemini_api_key)

SYSTEM_PROMPT = """Eres PatentBot, un asistente especializado en patentes tecnológicas para la plataforma PatentScope.

Tu rol es ayudar a ingenieros, diseñadores e investigadores a entender patentes, analizar tendencias tecnológicas y explorar el estado del arte en un campo específico.

Cuando el usuario busca algo, se te proporciona el contexto de los resultados encontrados (lista de patentes con título, abstract, clasificaciones, solicitante, etc.). Usa ese contexto para responder preguntas específicas sobre esas patentes.

IMPORTANTE: Cuando menciones patentes específicas en tu respuesta, sigue estas reglas:
- SIEMPRE escribe el número de patente como enlace markdown: [NUMERO_PATENTE](/patentes/ID)
- Cuando menciones 2 o más patentes relevantes, preséntelas como lista antes de explicar, así:

Las patentes:
- [EP4208230B1](/patentes/42)
- [US1234567A1](/patentes/7)

describen/comparten/muestran [explicación]...

Siempre deja una línea en blanco entre el último ítem de la lista y el texto que sigue.

El ID numérico está disponible en el contexto de cada patente. Úsalo siempre.

Responde siempre en el mismo idioma en que el usuario escribe (español o inglés).
Sé conciso, técnico pero accesible. No inventes información que no esté en el contexto."""


class Message(BaseModel):
    role: str  # "user" | "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    patents_context: list[dict] = []


class ChatResponse(BaseModel):
    reply: str


def _build_context_block(patents: list[dict]) -> str:
    if not patents:
        return ""
    single = len(patents) == 1
    lines = ["### Patente en detalle:" if single else "### Patentes en contexto (resultados de búsqueda):"]
    ab_limit = None if single else 200
    for i, p in enumerate(patents[:20], 1):
        pid = p.get("id")
        ti = p.get("ti") or "Sin título"
        pn = p.get("pn") or ""
        ab = (p.get("ab") or "") if ab_limit is None else (p.get("ab") or "")[:ab_limit]
        apc = p.get("apc") or p.get("pc") or ""
        cpc = p.get("cpc") or ""
        pd = p.get("pd") or ""
        if single:
            ic = p.get("ic") or ""
            ww = p.get("ww") or p.get("ws") or ""
            status = p.get("lg_st") or p.get("ls") or ""
            desc = (p.get("descripcion") or "")[:4000]
            claims = (p.get("claimen") or "")[:3000]
            lines.append(
                f"\n{pn} — {ti}"
                + (f"\nID: {pid}" if pid else "")
                + (f"\nSolicitante: {apc}" if apc else "")
                + (f"\nFecha: {pd}" if pd else "")
                + (f"\nEstado: {status}" if status else "")
                + (f"\nTema: {ww}" if ww else "")
                + (f"\nClasificación CPC: {cpc}" if cpc else "")
                + (f"\nClasificación IPC: {ic}" if ic else "")
                + (f"\nAbstract: {ab}" if ab else "")
                + (f"\nDescripción: {desc}" if desc else "")
                + (f"\nReivindicaciones: {claims}" if claims else "")
            )
        else:
            lines.append(
                f"\n[{i}] ID={pid} | {pn} — {ti}"
                + (f"\n    Solicitante: {apc}" if apc else "")
                + (f"\n    Fecha: {pd}" if pd else "")
                + (f"\n    CPC: {cpc}" if cpc else "")
                + (f"\n    Abstract: {ab}" if ab else "")
            )
    return "\n".join(lines)


@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest):
    context_block = _build_context_block(req.patents_context)

    system_with_context = SYSTEM_PROMPT
    if context_block:
        system_with_context += f"\n\n{context_block}"

    history_for_gemini = []
    for msg in req.history:
        role = "user" if msg.role == "user" else "model"
        history_for_gemini.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    contents = [
        *history_for_gemini,
        types.Content(role="user", parts=[types.Part(text=req.message)]),
    ]
    config = types.GenerateContentConfig(system_instruction=system_with_context)

    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=contents,
                config=config,
            )
            return ChatResponse(reply=response.text)
        except ClientError as e:
            if "429" in str(e) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            logger.error("Gemini ClientError: %s", e)
            raise HTTPException(status_code=502, detail="El asistente está ocupado, intenta en unos segundos.")
        except Exception as e:
            logger.error("Chat error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))
