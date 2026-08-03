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