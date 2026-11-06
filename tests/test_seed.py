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
