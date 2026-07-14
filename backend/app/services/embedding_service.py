"""Carga perezosa (lazy) y cacheada del modelo Sentence-BERT.

Cargar el modelo cuesta ~3 segundos la primera vez. Una vez en memoria, cada
embedding cuesta ~30-80 ms en CPU. Por eso lo guardamos como singleton: la
primera request paga el coste, las siguientes ya no.
"""

from __future__ import annotations

from threading import Lock

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None
_lock = Lock()


def get_model() -> SentenceTransformer:
    """Devuelve la instancia única del modelo. Thread-safe."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def encode_query(text: str) -> list[float]:
    """Genera el embedding (384 dim, normalizado) de una query del usuario."""
    model = get_model()
    vector = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vector.tolist()
