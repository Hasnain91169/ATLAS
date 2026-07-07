from atlas.llm.base import LLMClient
from atlas.prediction.assess import assess_reaction


class FakeLLM(LLMClient):
    def __init__(self, response: str):
        self._response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response


def test_no_llm_uses_heuristic():
    # Neutral text -> heuristic LOW.
    verdict, score = assess_reaction("A calm, welcome update.", "req", llm=None)
    assert verdict == "LOW"


def test_llm_classification_used():
    llm = FakeLLM('{"verdict":"HIGH","risk_score":0.82,"rationale":"backlash"}')
    verdict, score = assess_reaction("neutral looking report", "How will they react?", llm)
    assert verdict == "HIGH"
    assert score == 0.82
    # The requirement and report both reach the model.
    assert "How will they react?" in llm.prompts[0]


def test_llm_score_is_clamped():
    llm = FakeLLM('{"verdict":"MEDIUM","risk_score":9.0}')
    _, score = assess_reaction("report", "req", llm)
    assert score == 1.0


def test_invalid_llm_json_falls_back_to_heuristic():
    llm = FakeLLM("not json at all")
    # Report is loaded with backlash terms so the heuristic returns HIGH.
    text = "outrage backlash boycott protest anger criticism controversy"
    verdict, _ = assess_reaction(text, "req", llm)
    assert verdict == "HIGH"


def test_bad_verdict_falls_back_to_heuristic():
    llm = FakeLLM('{"verdict":"CATASTROPHIC","risk_score":0.9}')
    verdict, _ = assess_reaction("a mild, positive note", "req", llm)
    assert verdict == "LOW"
