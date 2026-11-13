from app import keywords
from app.seed import EXTRA_INFO


def items(*pairs):
    return [{"tema": "T", "pregunta": question, "respuesta": answer} for question, answer in pairs]


def test_normalize_removes_accents_and_case():
    assert keywords.normalize("Fútbol ÁGIL") == "futbol agil"


def test_stems_ignore_common_words_and_share_roots():
    assert keywords.stems("¿Qué tal programas?") == keywords.stems("programar tal")
    assert "manu" not in keywords.stems("¿Sabe Manuel Docker?")


def test_rank_puts_the_most_related_first_and_keeps_everything():
    data = items(
        ("¿Inglés?", "Tengo un B2."),
        ("¿Carnet de conducir?", "Me lo estoy sacando."),
        ("¿Tiempo libre?", "Juego al fútbol."),
    )
    ranked = keywords.rank(data, "¿Tienes carnet?")
    assert ranked[0]["pregunta"] == "¿Carnet de conducir?"
    assert len(ranked) == 3


def test_rank_matches_without_accents_and_prefers_the_question():
    data = items(
        ("¿Logro personal?", "Mi progreso en el futbol sala."),
        ("¿Tiempo libre?", "Juego al fútbol desde los 4 años."),
        ("¿Fútbol?", "Soy portero."),
    )
    assert keywords.rank(data, "¿futbol?")[0]["pregunta"] == "¿Fútbol?"


def test_ties_keep_the_original_order():
    data = items(("Uno", "a"), ("Dos", "b"))
    assert [i["pregunta"] for i in keywords.rank(data, "nada que ver")] == ["Uno", "Dos"]


def test_real_data_finds_python_start():
    data = [
        {"tema": i["topic"], "pregunta": i["question"], "respuesta": i["answer"]}
        for i in EXTRA_INFO
        if not i["fixed_answer"]
    ]
    top = [i["pregunta"] for i in keywords.rank(data, "¿Desde cuándo usas Python?")[:3]]
    assert "¿Desde cuándo usas Python?" in top
