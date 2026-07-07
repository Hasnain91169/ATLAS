from atlas.prediction.models import PredictionSeed, SeedDocument, derive_verdict
from atlas.prediction.stub import StubPredictionClient


def _seed(text):
    return PredictionSeed(
        requirement="How will the audience react?",
        documents=[SeedDocument(filename="msg.md", content=text)],
    )


def test_stub_is_deterministic():
    client = StubPredictionClient()
    seed = _seed("A calm, positive announcement.")
    assert client.simulate(seed).model_dump() == client.simulate(seed).model_dump()


def test_stub_low_risk_neutral_message():
    result = StubPredictionClient().simulate(_seed("We are opening a new library."))
    assert result.verdict == "LOW"
    assert result.simulation_id == "stub-sim"


def test_derive_verdict_high_on_backlash():
    text = (
        "outrage and backlash; boycott and protest; criticism, anger, "
        "controversy and distrust"
    )
    verdict, score = derive_verdict(text)
    assert verdict == "HIGH"
    assert score >= 0.7


def test_derive_verdict_medium_band():
    verdict, _ = derive_verdict("some concern and minor criticism")
    assert verdict == "MEDIUM"
