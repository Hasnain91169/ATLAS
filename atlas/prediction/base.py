from abc import ABC, abstractmethod

from atlas.prediction.models import PredictionResult, PredictionSeed


class PredictionClient(ABC):
    @abstractmethod
    def simulate(self, seed: PredictionSeed) -> PredictionResult:
        raise NotImplementedError
