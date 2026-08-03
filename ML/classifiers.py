import logging
from dataclasses import dataclass, field
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier as SklearnGBC
from sklearn.ensemble import RandomForestClassifier as SklearnRFC
from sklearn.linear_model import LogisticRegression as SklearnLR
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KNeighborsClassifier as SklearnKNN
from sklearn.svm import SVC as SklearnSVC
from base_models import BaseClassifier

logger = logging.getLogger(__name__)


@dataclass
class SVMClassifierModel(BaseClassifier):
    """Svm classifier strong default for MFCC style features"""

    tune_hyperparameters: bool = True
    param_grid: dict = field(default_factory=lambda: {
        "C": [1, 10, 100],
        "kernel": ["rbf", "linear"],
        "gamma": ["scale", "auto"],
    })
    cv: int = 3
    random_state: int = 42
    _model: SklearnSVC | GridSearchCV = field(init=False, repr=False)

    def __post_init__(self) -> None:
        base = SklearnSVC(probability=True, random_state=self.random_state)
        if self.tune_hyperparameters:
            self._model = GridSearchCV(base, self.param_grid, cv=self.cv, scoring="f1_macro", n_jobs=-1)
        else:
            self._model = base

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SVMClassifierModel":
        logger.info("SVMClassifierModel: fitting on %d samples, %d features", X.shape[0], X.shape[1])
        self._model.fit(X, y)
        if isinstance(self._model, GridSearchCV):
            logger.info("SVMClassifierModel: best params=%s", self._model.best_params_)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)