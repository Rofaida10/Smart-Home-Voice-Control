"""Audio In w Out and feature extraction

Central place for anything sound-related so the rest of the codebase just calls `extract_features(filepath)` allatol
without worrying about the librosa/MFCC details
"""

import logging
import numpy as np
from features import N_MFCC, SAMPLE_RATE
logger = logging.getLogger(__name__)


class AudioLoader:
    """Loads a .wav file as a mono signal at a fixed sample rate"""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def load(self, filepath: str) -> tuple[np.ndarray, int]:
        import librosa

        signal, sr = librosa.load(filepath, sr=self.sample_rate, mono=True)
        return signal, sr

class FeatureExtractor:
    """Extracts a fixed-length MFCC feature vector from a raw audio signal"""

    def __init__(self, n_mfcc: int = N_MFCC, sample_rate: int = SAMPLE_RATE):
        self.n_mfcc = n_mfcc
        self.sample_rate = sample_rate

    def extract(self, signal: np.ndarray, sr: int) -> np.ndarray:
        import librosa

        mfcc = librosa.feature.mfcc(y=signal, sr=sr, n_mfcc=self.n_mfcc)
        """Average over time so every clip means one fixed-length vector
        regardless of how long the recording was"""

        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)
        return np.concatenate([mfcc_mean, mfcc_std])