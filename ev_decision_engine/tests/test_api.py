import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import storage
from api import health, post_decide
from tests.helpers import make_message


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(storage, "engine", engine)
    monkeypatch.setattr(storage, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    storage.Base.metadata.create_all(engine)
    yield


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_decide_returns_decision_and_logs_it() -> None:
    message = make_message(confidence=0.9, severity=0.9, criticality=0.9)
    response = post_decide(message, blast_radius=1)
    body = json.loads(bytes(response.body))
    assert body["chosen_action"] in body["action_scores"]

    with storage.get_session() as session:
        records = session.scalars(select(storage.IncidentRecord)).all()
    assert [r.incident_id for r in records] == ["test-1"]
    assert json.loads(records[0].decision_json) == body


def test_infinite_scores_serialize_as_null() -> None:
    message = make_message(confidence=0.9, severity=1.0, criticality=1.0, corroborating=4)
    body = json.loads(bytes(post_decide(message, blast_radius=3).body))
    assert all(v is None or isinstance(v, float) for v in body["action_scores"].values())
