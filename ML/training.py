import logging
from abc import ABC, abstractmethod
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from base_models import BaseClassifier, BaseEvaluator, ClassificationEvaluator
from classifiers import build_candidate_models
from features import COMMAND_COLUMN, FILEPATH_COLUMN, MIN_REQUIRED_F1, PERSON_COLUMN
from sounds import extract_features

logger = logging.getLogger(__name__)


### Data In w Out ((ISP)) TODO fill in once the CSV exists

class DataReader(ABC):
    @abstractmethod
    def load(self) -> pd.DataFrame:
        ...


class CsvDataReader(DataReader):
    """Reads the dataset CSV columns = filepath, person, command

    TODO : point `path` at the real CSV once recordings are
    collected and the csv is assembled (e.g. Data/recordings.csv).
    """

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
    """Turns the CSV rows into an audio feature matrix X and two label
vectors (speaker, command), extracting MFCCs only once per file."""

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
    """Stratified train/test split (kept consistent across both targets) + scaling"""

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