"""Audio In w Out and feature extraction

Central place for anything sound-related so the rest of the codebase just calls `extract_features(filepath)` allatol
without worrying about the librosa/MFCC details
"""

import logging
import numpy as np
from features import N_MFCC, SAMPLE_RATE
logger = logging.getLogger(__name__)

class AudioLoader:
    """Loads a .wav file as a mono signal at a fixed sample rate."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def load(self, filepath: str) -> tuple[np.ndarray, int]:
        import librosa

        signal, sr = librosa.load(filepath, sr=self.sample_rate, mono=True)
        return signal, sr