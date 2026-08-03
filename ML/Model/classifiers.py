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



@dataclass
class RandomForestClassifierModel(BaseClassifier):
    tune_hyperparameters: bool = True
    param_grid: dict = field(default_factory=lambda: {
        "n_estimators": [100, 200],
        "max_depth": [10, 20, None],
        "min_samples_leaf": [1, 3, 5],
    })
    cv: int = 3
    random_state: int = 42
    _model: SklearnRFC | GridSearchCV = field(init=False, repr=False)

    def __post_init__(self) -> None:
        base = SklearnRFC(random_state=self.random_state, n_jobs=-1)
        if self.tune_hyperparameters:
            self._model = GridSearchCV(base, self.param_grid, cv=self.cv, scoring="f1_macro", n_jobs=-1)
        else:
            self._model = base

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomForestClassifierModel":
        logger.info("RandomForestClassifierModel: fitting on %d samples, %d features", X.shape[0], X.shape[1])
        self._model.fit(X, y)
        if isinstance(self._model, GridSearchCV):
            logger.info("RandomForestClassifierModel: best params=%s", self._model.best_params_)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)




@dataclass
class GradientBoostingClassifierModel(BaseClassifier):
    tune_hyperparameters: bool = False
    n_estimators: int = 150
    learning_rate: float = 0.1
    max_depth: int = 3
    random_state: int = 42
    _model: SklearnGBC = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._model = SklearnGBC(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            max_depth=self.max_depth,
            random_state=self.random_state,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GradientBoostingClassifierModel":
        logger.info("GradientBoostingClassifierModel: fitting on %d samples, %d features", X.shape[0], X.shape[1])
        self._model.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)



@dataclass
class KNNClassifierModel(BaseClassifier):
    tune_hyperparameters: bool = True
    param_grid: dict = field(default_factory=lambda: {"n_neighbors": [3, 5, 7, 9]})
    cv: int = 3
    _model: SklearnKNN | GridSearchCV = field(init=False, repr=False)

    def __post_init__(self) -> None:
        base = SklearnKNN()
        if self.tune_hyperparameters:
            self._model = GridSearchCV(base, self.param_grid, cv=self.cv, scoring="f1_macro", n_jobs=-1)
        else:
            self._model = base

    def fit(self, X: np.ndarray, y: np.ndarray) -> "KNNClassifierModel":
        logger.info("KNNClassifierModel: fitting on %d samples, %d features", X.shape[0], X.shape[1])
        self._model.fit(X, y)
        if isinstance(self._model, GridSearchCV):
            logger.info("KNNClassifierModel: best params=%s", self._model.best_params_)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)
    

@dataclass
class LogisticRegressionClassifierModel(BaseClassifier):
    max_iter: int = 2000
    random_state: int = 42
    _model: SklearnLR = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._model = SklearnLR(max_iter=self.max_iter, random_state=self.random_state)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogisticRegressionClassifierModel":
        logger.info("LogisticRegressionClassifierModel: fitting on %d samples, %d features", X.shape[0], X.shape[1])
        self._model.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)


def build_candidate_models() -> dict[str, BaseClassifier]:
    """All algorithms to try per task. The pipeline picks whichever wins."""

    return {
        "SVM": SVMClassifierModel(),
        "Random Forest": RandomForestClassifierModel(),
        "Gradient Boosting": GradientBoostingClassifierModel(),
        "KNN": KNNClassifierModel(),
        "Logistic Regression": LogisticRegressionClassifierModel(),
    }