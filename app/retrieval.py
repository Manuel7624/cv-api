"""Búsqueda de la información extra relacionada con cada pregunta (RAG).

En vez de enviar al modelo las 70 respuestas extra en cada pregunta, se envían
solo las más parecidas a la pregunta. Para medir el parecido se usan embeddings
de Gemini: vectores de números que representan el significado de un texto.

- Los vectores de las respuestas se guardan en app/embeddings.json, en el
  repositorio. Al arrancar se leen de ahí y solo se calculan los de las respuestas
  nuevas o cambiadas, así que un arranque normal no gasta cupo de Gemini.
  Para regenerarlos a mano: python -m app.retrieval
- En cada pregunta se calcula el vector de la pregunta (y de las anteriores, para
  entender las de seguimiento) y se eligen las respuestas más parecidas.
- Aunque el parecido sea bajo (saludos, texto sin sentido, preguntas que no tratan
  de Manuel), se envían igualmente las más parecidas: esas preguntas se responden
  con las reglas, sin datos extra. Si la IA dice que no tiene el dato, el chat
  repite la pregunta con toda la información (plan B).
- Si la búsqueda falla, se devuelve None y el chat envía todas.
"""
import hashlib
import json
import logging
import math
import os
from pathlib import Path

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
TIMEOUT_SECONDS = 10  # al calcular los vectores de las respuestas (python -m app.retrieval)
QUERY_TIMEOUT_SECONDS = 2.5  # al buscar por cada pregunta del chat: si tarda más, plan B

# Cuántas respuestas se envían. Por debajo de MIN_SIMILARITY (de -1 a 1) se avisa en
# los logs de que el parecido es bajo, pero se envían igual.
TOP_K = 12
MIN_SIMILARITY = 0.65
# Vectores ya calculados, guardados por el texto exacto de cada respuesta.
CACHE_PATH = Path(__file__).parent / "embeddings.json"
# Decimales que se guardan: de sobra para comparar vectores y el archivo pesa menos.
CACHE_DECIMALS = 5

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


def embed(texts: list[str], timeout: float = TIMEOUT_SECONDS) -> list[list[float]]:
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
                timeout=timeout,
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
        """Usa los vectores guardados y calcula solo los que falten."""
        texts = [document_text(item) for item in items]
        cached = load_cache()
        missing = [text for text in texts if text_key(text) not in cached]
        if missing:
            logger.info("RAG: calculando %d vectores nuevos o cambiados", len(missing))
            for text, vector in zip(missing, embed(missing)):
                cached[text_key(text)] = vector
            save_cache({text_key(text): cached[text_key(text)] for text in texts})
        return cls(items, [cached[text_key(text)] for text in texts])

    def search(
        self, message: str, previous_questions: list[str]
    ) -> tuple[list[dict[str, str]], float]:
        """Devuelve las TOP_K respuestas más parecidas y el parecido de la mejor."""
        query = embed([query_text(message, previous_questions)], QUERY_TIMEOUT_SECONDS)[0]
        scores = [similarity(query, vector) for vector in self.vectors]
        best = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:TOP_K]
        # Se mantienen en su orden original para que el texto se lea con sentido.
        return [self.items[i] for i in sorted(best)], scores[best[0]] if best else -1.0


def text_key(text: str) -> str:
    """Identifica cada texto: si la respuesta cambia, cambia su clave."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cache() -> dict[str, list[float]]:
    """Lee los vectores guardados. Si no sirven (otro modelo, archivo roto), ninguno."""
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if data["model"] != EMBEDDING_MODEL or data["dimensions"] != DIMENSIONS:
            return {}
        return {key: normalize(vector) for key, vector in data["vectors"].items()}
    except (OSError, ValueError, KeyError, TypeError, RetrievalError):
        return {}


def save_cache(vectors: dict[str, list[float]]) -> None:
    """Guarda los vectores. Si no se puede escribir, el RAG funciona igual."""
    data = {
        "model": EMBEDDING_MODEL,
        "dimensions": DIMENSIONS,
        "vectors": {
            key: [round(value, CACHE_DECIMALS) for value in vector]
            for key, vector in sorted(vectors.items())
        },
    }
    try:
        CACHE_PATH.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    except OSError as error:
        logger.warning("No se han podido guardar los vectores: %s", error)


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
    """Respuestas extra para esta pregunta, o None si no hay búsqueda (plan B)."""
    if index is None:
        return None
    try:
        selected, best_score = index.search(message, previous_questions)
    except RetrievalError as error:
        logger.warning("La búsqueda del RAG ha fallado: %s", error)
        return None
    low = ", similitud baja" if best_score < MIN_SIMILARITY else ""
    logger.info("RAG: %d respuestas elegidas (mejor parecido %.2f%s)", len(selected), best_score, low)
    return selected


if __name__ == "__main__":
    # Regenera app/embeddings.json con las respuestas de app/seed.py.
    logging.basicConfig(level=logging.INFO)
    from app.seed import EXTRA_INFO

    build_index([
        {"tema": item["topic"], "pregunta": item["question"], "respuesta": item["answer"]}
        for item in EXTRA_INFO
        if not item["fixed_answer"]
    ])
    print("Vectores listos" if index else "No se han podido calcular los vectores")
