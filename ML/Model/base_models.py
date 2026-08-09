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
    """Abstraction model evaluation"""

    @abstractmethod
    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        ...

class ClassificationEvaluator(BaseEvaluator):
    """Computes standard classification metrics"""
 
    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
 
        accuracy = float(accuracy_score(y_true, y_pred))
        f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
        precision = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
        recall = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
 
        metrics = {"accuracy": accuracy, "f1": f1, "precision": precision, "recall": recall}
        logger.info(
            "ClassificationEvaluator: accuracy=%.4f  f1=%.4f  precision=%.4f  recall=%.4f",
            accuracy, f1, precision, recall,
        )
        return metrics