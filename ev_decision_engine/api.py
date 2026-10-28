"""FastAPI wrapper around policy.decide(), logging each decision to SQLite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Response

from policy import decide
from schemas import Message
from storage import IncidentRecord, get_session, init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="EV Decision Engine", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/decide")
def post_decide(message: Message, blast_radius: int = Query(default=1, ge=1)) -> Response:
    decision = decide(message, blast_radius=blast_radius)
    # Serialize via pydantic directly: candidates excluded by the high-impact routing
    # score -inf, which pydantic emits as null but Starlette's JSON encoder rejects.
    decision_json = decision.model_dump_json()

    with get_session() as session:
        session.add(
            IncidentRecord(
                incident_id=message.event.correlation_id,
                payload_json=message.model_dump_json(),
                decision_json=decision_json,
            )
        )

    return Response(content=decision_json, media_type="application/json")
