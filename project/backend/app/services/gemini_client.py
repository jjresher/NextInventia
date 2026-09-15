"""
Cliente de Gemini con fallback en cascada entre modelos.

Cada modelo tiene sus propios límites reales de RPM (requests por minuto)
y RPD (requests por día). El límite se respeta exacto, sin margen de
seguridad artificial: si el límite es 10, se permiten 10 peticiones y
la número 11 pasa al siguiente modelo.

TPM (tokens por minuto) no se controla aquí porque en la práctica el
cuello de botella real son RPM/RPD, no TPM (250K TPM es difícil de
agotar con prompts cortos de clasificación).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock

from google import genai
from google.genai.errors import ClientError
from google.genai.types import ContentListUnion


# ---------------------------------------------------------------------------
# Configuración de límites reales por modelo (free tier)
# Ajustar estos valores si Google cambia las cuotas.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelLimits:
    name: str
    rpm: int   # requests por minuto
    rpd: int   # requests por día


# Orden = orden de preferencia del fallback (el primero es el que se intenta primero)
MODEL_CASCADE: list[ModelLimits] = [
    ModelLimits(name="gemini-3.5-flash-lite", rpm=15, rpd=500),
    ModelLimits(name="gemini-3.1-flash-lite", rpm=15, rpd=500),
    ModelLimits(name="gemini-2.5-flash-lite", rpm=10, rpd=20),
]


# ---------------------------------------------------------------------------
# Rate limiter por modelo (sliding window real, no aproximado)
# ---------------------------------------------------------------------------

class _ModelRateLimiter:
    """Lleva la cuenta exacta de peticiones por minuto y por día para UN modelo."""

    def __init__(self, limits: ModelLimits):
        self.limits = limits
        self._minute_window: deque[float] = deque()
        self._day_window: deque[float] = deque()
        self._lock = Lock()

    def _purge_old(self, now: float) -> None:
        # Ventana deslizante de 60s para RPM
        while self._minute_window and now - self._minute_window[0] >= 60:
            self._minute_window.popleft()
        # Ventana deslizante de 24h para RPD (reset real es a medianoche Pacific,
        # pero una ventana deslizante de 24h es un proxy seguro y simple)
        while self._day_window and now - self._day_window[0] >= 86400:
            self._day_window.popleft()

    def try_reserve(self) -> bool:
        """Si hay cupo, reserva una petición atómicamente y devuelve True.

        Chequear con has_capacity() y llamar record_request() por separado
        deja una ventana entre ambas llamadas: dos threads pueden pasar el
        chequeo antes de que cualquiera registre su petición y el límite
        real se termina excediendo. Por eso esto va bajo un único lock.
        """
        with self._lock:
            now = time.monotonic()
            self._purge_old(now)
            if (
                len(self._minute_window) >= self.limits.rpm
                or len(self._day_window) >= self.limits.rpd
            ):
                return False
            self._minute_window.append(now)
            self._day_window.append(now)
            return True

    def status(self) -> dict:
        with self._lock:
            now = time.monotonic()
            self._purge_old(now)
            return {
                "model": self.limits.name,
                "rpm_used": len(self._minute_window),
                "rpm_limit": self.limits.rpm,
                "rpd_used": len(self._day_window),
                "rpd_limit": self.limits.rpd,
            }


# ---------------------------------------------------------------------------
# Cliente con fallback en cascada
# ---------------------------------------------------------------------------

class GeminiFallbackClient:
    def __init__(self, api_key: str, cascade: list[ModelLimits] | None = None):
        self._client = genai.Client(api_key=api_key)
        self._cascade = cascade or MODEL_CASCADE
        self._limiters = {m.name: _ModelRateLimiter(m) for m in self._cascade}

    def status(self) -> list[dict]:
        """Útil para debug: muestra el uso actual de cada modelo en la cascada."""
        return [self._limiters[m.name].status() for m in self._cascade]

    def generate(self, contents: ContentListUnion, **generate_kwargs) -> str:
        """
        Intenta generar contenido probando cada modelo de la cascada en orden.

        `contents` acepta lo mismo que `generate_content` de google-genai: un
        string simple (prompt de una sola vuelta) o una lista de `types.Content`
        (historial multi-turno, como usa el chat).

        - Si un modelo ya agotó su cuota local (según nuestro conteo), se salta
          sin siquiera llamar a la API (ahorra una llamada perdida).
        - Si un modelo devuelve 429 real (cuota agotada en el lado de Google,
          por ejemplo por otro proceso usando la misma key), se marca como
          agotado y se pasa al siguiente igual.
        - Cualquier otro error (400, 500, etc.) se relanza inmediatamente,
          porque no es un problema de cuota y cambiar de modelo no lo arregla.
        """
        last_error: Exception | None = None

        for model_limits in self._cascade:
            limiter = self._limiters[model_limits.name]

            if not limiter.try_reserve():
                # Ya sabemos localmente que este modelo está al límite exacto.
                # No perdemos una llamada real intentándolo.
                continue

            try:
                response = self._client.models.generate_content(
                    model=model_limits.name,
                    contents=contents,
                    **generate_kwargs,
                )
                return response.text

            except ClientError as e:
                if getattr(e, "code", None) == 429:
                    # La cuota real de Google ya se agotó para este modelo
                    # (puede pasar aunque nuestro contador local diga que
                    # había cupo, por ejemplo si otro proceso comparte la key).
                    last_error = e
                    continue
                raise  # error real de la API, no de cuota: no tiene sentido cambiar de modelo

        raise RuntimeError(
            "Todos los modelos de la cascada agotaron su cuota "
            f"(RPM/RPD). Último error: {last_error}"
        )
