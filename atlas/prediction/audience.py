from __future__ import annotations

from pathlib import Path

from atlas.prediction.base import PredictionClient
from atlas.prediction.models import PredictionResult, PredictionSeed, SeedDocument
from atlas.storage.sqlite import insert_audience_forecast


def build_seed(
    requirement: str,
    documents: list[SeedDocument],
    project_name: str | None = None,
    additional_context: str | None = None,
) -> PredictionSeed:
    return PredictionSeed(
        requirement=requirement,
        documents=documents,
        project_name=project_name,
        additional_context=additional_context,
    )


def load_document(path: Path) -> SeedDocument:
    return SeedDocument(filename=path.name, content=path.read_text(encoding="utf-8"))


def predict_audience(
    client: PredictionClient, conn, seed: PredictionSeed
) -> PredictionResult:
    result = client.simulate(seed)
    insert_audience_forecast(conn, seed.requirement, result)
    return result
