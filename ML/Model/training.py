import logging
from abc import ABC, abstractmethod
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from base_models import BaseClassifier, BaseEvaluator, ClassificationEvaluator
from classifiers import build_candidate_models
from features import COMMAND_COLUMN, FILEPATH_COLUMN, MIN_REQUIRED_F1, PERSON_COLUMN
from sounds import extract_features

logger = logging.getLogger(__name__)


# Data In Out

class DataReader(ABC):
    @abstractmethod
    def load(self) -> pd.DataFrame:
        ...


class CsvDataReader(DataReader):
    """Reads the dataset CSV: columns = filepath, person, command"""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> pd.DataFrame:
        logger.info("Loading dataset from %s", self.path)
        df = pd.read_csv(self.path)
        required = {FILEPATH_COLUMN, PERSON_COLUMN, COMMAND_COLUMN}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return df


# Feature preparation

class FeaturePreparer:
    """Turns the CSV rows into an audio feature matrix X and two label vectors (speaker, command)
    extracting MFCCs only once per file"""

    def __init__(self):
        self.person_encoder = LabelEncoder()
        self.command_encoder = LabelEncoder()

    def prepare(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        logger.info("FeaturePreparer: extracting features for %d recordings", len(df))
        X = np.vstack([extract_features(fp) for fp in df[FILEPATH_COLUMN]])

        y_speaker = self.person_encoder.fit_transform(df[PERSON_COLUMN])
        y_command = self.command_encoder.fit_transform(df[COMMAND_COLUMN])

        logger.info("FeaturePreparer: X shape=%s", X.shape)
        return X, y_speaker, y_command


class DataSplitter:
    """Stratified train and test split (kept consistent across both targets) + scaling"""

    def __init__(self, test_size: float = 0.2, random_state: int = 42):
        self.test_size = test_size
        self.random_state = random_state

    def split(self, X: np.ndarray, y_speaker: np.ndarray, y_command: np.ndarray):
        # Stratify jointly on (speaker, command) so every combination is represented proportionally in train and test
        strat_key = [f"{s}_{c}" for s, c in zip(y_speaker, y_command)]

        idx_train, idx_test = train_test_split(
            np.arange(len(X)),
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=strat_key,
        )

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X[idx_train])
        X_test = scaler.transform(X[idx_test])

        logger.info("DataSplitter: train=%d  test=%d", len(X_train), len(X_test))
        return (
            X_train, X_test,
            y_speaker[idx_train], y_speaker[idx_test],
            y_command[idx_train], y_command[idx_test],
            scaler,
        )


# Multi-model training per task

class CrossValidationChecker:
    """Runs k-fold cross-validation on the FULL dataset per model

    A single train and test split can look perfect by luck ama Cross-validation trains and evaluates on k different
    splits and reports mean +- (positive or negaative) std which is a much more trustworthy signal
    for whether a "1.0" score is real or a fluke
    """

    def __init__(self, task_name: str, n_splits: int = 5, random_state: int = 42):
        self.task_name = task_name
        self.n_splits = n_splits
        self.random_state = random_state

    def run(self, X: np.ndarray, y: np.ndarray) -> None:
        cv = StratifiedKFold(n_splits=self.n_splits, shuffle=True, random_state=self.random_state)
        models = build_candidate_models()

        print(f"{self.n_splits} fold cross validation ({self.task_name})")
        for name, model in models.items():
            # cross_val_score needs a plain estimator not our dataclass wrapper so we reach into the underlying sklearn model
            estimator = getattr(model, "_model", model)
            scores = cross_val_score(estimator, X, y, cv=cv, scoring="f1_macro", n_jobs=-1)
            print(f"    [{self.task_name}] {name:<20} "
                  f"f1={scores.mean():.4f} (+/- {scores.std():.4f})  folds={np.round(scores, 3)}")
        print()


class TaskTrainingPipeline:
    """Trains every candidate model for a single task (e.g. 'speaker' or
    'command'), evaluates them, and keeps the best one by F1 score"""

    def __init__(self, evaluator: BaseEvaluator, task_name: str):
        self.evaluator = evaluator
        self.task_name = task_name

    def run(self, X_train, X_test, y_train, y_test) -> tuple[str, BaseClassifier, dict]:
        results = {}
        models = build_candidate_models()

        for name, model in models.items():
            model.fit(X_train, y_train)
            test_pred = model.predict(X_test)
            metrics = self.evaluator.evaluate(y_test, test_pred)
            results[name] = {"model": model, "metrics": metrics}
            print(f"  [{self.task_name}] {name:<20} "
                  f"accuracy={metrics['accuracy']:.4f}  f1={metrics['f1']:.4f}")

        best_name = max(results, key=lambda n: results[n]["metrics"]["f1"])
        best = results[best_name]

        status = "OK" if best["metrics"]["f1"] >= MIN_REQUIRED_F1 else "BELOW TARGET"
        print(f"  → best for [{self.task_name}]: {best_name} "
              f"(f1={best['metrics']['f1']:.4f}, target={MIN_REQUIRED_F1}) [{status}]\n")

        return best_name, best["model"], best["metrics"]


class ModelWriter:
    def __init__(self, path: Path):
        self.path = path

    def save(self, artifact: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, self.path)
        logger.info("Model artifact saved to %s", self.path)

# Entry point

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    BASE_DIR = Path(__file__).resolve().parents[1]
    data_path = BASE_DIR / "Data" / "recordings.csv"
    artifacts_dir = BASE_DIR / "Model" / "artifacts"

    reader = CsvDataReader(data_path)
    preparer = FeaturePreparer()
    splitter = DataSplitter(test_size=0.2, random_state=42)
    evaluator = ClassificationEvaluator()

    df = reader.load()
    X, y_speaker, y_command = preparer.prepare(df)
    (
        X_train, X_test,
        y_speaker_train, y_speaker_test,
        y_command_train, y_command_test,
        scaler,
    ) = splitter.split(X, y_speaker, y_command)

    # Scale the FULL dataset (not just train) to feed cross-validation
    # this checks whether a perfect score holds up across many random splits not just the one 80/20 split used below.

    X_full_scaled = StandardScaler().fit_transform(X)

    print("\nRobustness check (cross-validation on full dataset)")
    CrossValidationChecker(task_name="speaker").run(X_full_scaled, y_speaker)
    CrossValidationChecker(task_name="command").run(X_full_scaled, y_command)

    print("\nSpeaker Identification: model comparison")
    speaker_pipeline = TaskTrainingPipeline(evaluator, task_name="speaker")
    speaker_best_name, speaker_best_model, speaker_metrics = speaker_pipeline.run(
        X_train, X_test, y_speaker_train, y_speaker_test
    )

    print("\nCommand Classification: model comparison")
    command_pipeline = TaskTrainingPipeline(evaluator, task_name="command")
    command_best_name, command_best_model, command_metrics = command_pipeline.run(
        X_train, X_test, y_command_train, y_command_test
    )

    ModelWriter(artifacts_dir / "speaker_model.joblib").save({
        "model_name": speaker_best_name,
        "model": speaker_best_model,
        "scaler": scaler,
        "label_encoder": preparer.person_encoder,
        "metrics": speaker_metrics,
    })
    ModelWriter(artifacts_dir / "command_model.joblib").save({
        "model_name": command_best_name,
        "model": command_best_model,
        "scaler": scaler,
        "label_encoder": preparer.command_encoder,
        "metrics": command_metrics,
    })

    print("\nFinal Results")
    print(f"Speaker ID:   {speaker_best_name:<20} f1={speaker_metrics['f1']:.4f}")
    print(f"Command:      {command_best_name:<20} f1={command_metrics['f1']:.4f}")