import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import models
from app.seed import seed


def test_seed_does_not_duplicate_data(db_session):
    """db_session ya viene cargada: una segunda carga no debe añadir nada."""
    seed(db_session)
    assert db_session.scalar(select(func.count()).select_from(models.Profile)) == 1
    assert db_session.scalar(select(func.count()).select_from(models.Experience)) == 2


def test_foreign_keys_are_enforced(db_session):
    db_session.add(models.ExperienceHighlight(experience_id=999, text="x", position=0))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_extra_info_answers_are_short_plain_text():
    """El chat responde en 100 palabras como mucho y sin Markdown: si los datos ya
    cumplen eso, ningún proveedor los copia largos o con listas."""
    from app.seed import EXTRA_INFO

    for item in EXTRA_INFO:
        assert len(item["answer"].split()) <= 100, item["question"]
        assert "**" not in item["answer"], item["question"]
        assert "\n- " not in item["answer"] and not item["answer"].startswith("- "), item["question"]
