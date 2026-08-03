import logging
from abc import ABC, abstractmethod
import numpy as np

logger = logging.getLogger(__name__)

class BaseClassifier(ABC):
    """Abstraction for classification models"""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseClassifier":
        ...
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

class BaseEvaluator(ABC):
    """Abstraction for model evaluation"""

    @abstractmethod
    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        ...