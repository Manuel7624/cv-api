"""Búsqueda de la información extra relacionada con cada pregunta (RAG).

En vez de enviar al modelo las 70 respuestas extra en cada pregunta, se envían
solo las más parecidas a la pregunta. Para medir el parecido se usan embeddings
de Gemini: vectores de números que representan el significado de un texto.

- Al arrancar se calculan los vectores de todas las respuestas, una sola vez.
- En cada pregunta se calcula el vector de la pregunta (y de las anteriores, para
  entender las de seguimiento) y se eligen las respuestas más parecidas.
- Si algo falla o el parecido es bajo, se devuelve None y el chat envía todas.
"""
import logging
import math
import os

import httpx

logger = logging.getLogger("uvicorn.error")

# Poner a False para desactivar el RAG y enviar siempre toda la información.
ENABLED = True

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBEDDING_MODEL}:batchEmbedContents"
)
DIMENSIONS = 768
MAX_TEXTS_PER_REQUEST = 100
TIMEOUT_SECONDS = 10

# Cuántas respuestas se envían y parecido mínimo (de -1 a 1) para fiarse de la búsqueda.
TOP_K = 12
MIN_SIMILARITY = 0.65
# Preguntas anteriores del usuario que se añaden a la búsqueda.
PREVIOUS_QUESTIONS = 2


class RetrievalError(Exception):
    """La búsqueda no ha podido hacerse."""


def normalize(vector: list[float]) -> list[float]:
    """Deja el vector con longitud 1, para que el producto escalar sea el coseno."""
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        raise RetrievalError("vector vacío")
    return [value / length for value in vector]


def similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def embed(texts: list[str]) -> list[list[float]]:
    """Pide a Gemini los vectores de varios textos, en el mismo orden."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RetrievalError("falta la clave")

    vectors = []
    for start in range(0, len(texts), MAX_TEXTS_PER_REQUEST):
        requests = [
            {
                "model": f"models/{EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": DIMENSIONS,
            }
            for text in texts[start:start + MAX_TEXTS_PER_REQUEST]
        ]
        try:
            response = httpx.post(
                EMBEDDING_URL,
                headers={"x-goog-api-key": api_key},
                json={"requests": requests},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            vectors += [item["values"] for item in response.json()["embeddings"]]
        except httpx.HTTPStatusError as error:
            raise RetrievalError(f"respuesta {error.response.status_code}") from None
        except httpx.HTTPError as error:
            raise RetrievalError(type(error).__name__) from None
        except (KeyError, TypeError, ValueError):
            raise RetrievalError("respuesta con formato inesperado") from None

    if len(vectors) != len(texts):
        raise RetrievalError("faltan vectores")
    return [normalize(vector) for vector in vectors]


def document_text(item: dict[str, str]) -> str:
    # Formato que recomienda Google para los documentos con gemini-embedding-2.
    return f"title: {item['pregunta']} | text: {item['respuesta']}"


def query_text(message: str, previous_questions: list[str]) -> str:
    text = " ".join([*previous_questions[-PREVIOUS_QUESTIONS:], message])
    return f"task: search result | query: {text}"


class ExtraInfoIndex:
    """Respuestas extra con sus vectores, calculados una sola vez."""

    def __init__(self, items: list[dict[str, str]], vectors: list[list[float]]) -> None:
        self.items = items
        self.vectors = vectors

    @classmethod
    def build(cls, items: list[dict[str, str]]) -> "ExtraInfoIndex":
        return cls(items, embed([document_text(item) for item in items]))

    def search(self, message: str, previous_questions: list[str]) -> list[dict[str, str]] | None:
        """Devuelve las TOP_K respuestas más parecidas, o None si ninguna se parece."""
        query = embed([query_text(message, previous_questions)])[0]
        scores = [similarity(query, vector) for vector in self.vectors]
        best = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:TOP_K]
        if not best or scores[best[0]] < MIN_SIMILARITY:
            return None
        # Se mantienen en su orden original para que el texto se lea con sentido.
        return [self.items[i] for i in sorted(best)]


index: ExtraInfoIndex | None = None


def build_index(items: list[dict[str, str]]) -> None:
    """Se llama al arrancar. Si falla, el chat funciona igual enviando todo."""
    global index
    index = None
    if not ENABLED or not items:
        return
    try:
        index = ExtraInfoIndex.build(items)
        logger.info("RAG listo: %d respuestas indexadas", len(items))
    except RetrievalError as error:
        logger.warning("RAG desactivado, no se han podido calcular los vectores: %s", error)


def select_extra_info(message: str, previous_questions: list[str]) -> list[dict[str, str]] | None:
    """Respuestas extra para esta pregunta, o None para enviar todas (plan B)."""
    if index is None:
        return None
    try:
        return index.search(message, previous_questions)
    except RetrievalError as error:
        logger.warning("La búsqueda del RAG ha fallado: %s", error)
        return None
