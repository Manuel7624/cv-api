"""Búsqueda por palabras clave, sin servicios externos.

Solo se usa cuando no hay embeddings (RAG) y la pregunta tiene que ir a un proveedor
con un límite de tokens que no admite toda la información (Groq). Ordena las
respuestas extra según cuántas palabras comparten con la pregunta.
"""
import math
import re
import unicodedata

# Palabras demasiado comunes para ayudar a distinguir unas respuestas de otras.
STOPWORDS = {
    "a", "al", "algo", "algun", "alguna", "alguno", "ante", "antes", "aqui", "asi", "cada",
    "como", "con", "cual", "cuales", "cuando", "cuanto", "cuantos", "cuanta", "cuantas",
    "de", "del", "desde", "donde", "durante", "e", "el", "ella", "ellas", "ellos", "en",
    "entre", "era", "eres", "es", "esa", "ese", "eso", "esta", "estas", "este", "esto",
    "estos", "fue", "ha", "has", "hay", "hace", "hasta", "la", "las", "le", "les", "lo",
    "los", "manuel", "mas", "me", "mi", "mis", "mucho", "muy", "nada", "ni", "no", "nos",
    "o", "os", "otra", "otro", "para", "pero", "poco", "por", "porque", "puede", "puedes",
    "que", "quien", "sabe", "sabes", "se", "si", "sin", "sobre", "son", "su", "sus",
    "tambien", "te", "tiene", "tienes", "tu", "tus", "un", "una", "uno", "unos", "y", "ya",
    "yo",
}
STEM_LENGTH = 4


def normalize(text: str) -> str:
    """Minúsculas y sin tildes, para que "Fútbol" y "futbol" coincidan."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def stems(text: str) -> set[str]:
    """Raíces de las palabras útiles: "programas" y "programar" comparten "prog"."""
    words = re.findall(r"[a-z0-9]+", normalize(text))
    return {word[:STEM_LENGTH] for word in words if word not in STOPWORDS and len(word) > 1}


def rank(items: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    """Devuelve todas las respuestas, de la más relacionada con la pregunta a la menos.

    Coincidir en la pregunta de la respuesta cuenta el doble que en el texto, y las
    palabras raras (que salen en pocas respuestas) cuentan más que las frecuentes.
    """
    query_stems = stems(query)
    question_stems = [stems(item["pregunta"]) for item in items]
    answer_stems = [stems(item["respuesta"]) for item in items]
    total = len(items)

    def weight(stem: str) -> float:
        appears_in = sum(stem in q or stem in a for q, a in zip(question_stems, answer_stems))
        return math.log((total + 1) / (appears_in + 1)) + 1

    weights = {stem: weight(stem) for stem in query_stems}
    scores = []
    for position in range(total):
        score = 0.0
        for stem, value in weights.items():
            if stem in question_stems[position]:
                score += 2 * value
            elif stem in answer_stems[position]:
                score += value
        scores.append(score)
    # sorted() mantiene el orden original cuando hay empate.
    order = sorted(range(total), key=lambda position: scores[position], reverse=True)
    return [items[position] for position in order]
