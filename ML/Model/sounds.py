"""Audio I/O and feature extraction.

Central place for anything sound-related, so the rest of the codebase
just calls `extract_features(filepath)` without worrying about the
librosa/MFCC details.
"""

import logging

import numpy as np

from features import N_MFCC, SAMPLE_RATE

logger = logging.getLogger(__name__)


class AudioLoader:
    """Loads a .wav file as a mono signal at a fixed sample rate, trims
    leading/trailing silence, and normalizes volume.

    Without this, two recordings of the same word can differ mainly in
    silence padding or mic loudness rather than the voice itself — which
    the model can latch onto instead of the actual speech content.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, top_db: int = 25):
        self.sample_rate = sample_rate
        self.top_db = top_db

    def load(self, filepath: str) -> tuple[np.ndarray, int]:
        import librosa

        signal, sr = librosa.load(filepath, sr=self.sample_rate, mono=True)

        # Trim silence from both ends.
        signal, _ = librosa.effects.trim(signal, top_db=self.top_db)

        # Peak-normalize so loudness differences between recordings/mics
        # don't become an accidental "feature".
        peak = np.max(np.abs(signal))
        if peak > 0:
            signal = signal / peak

        # Pre-emphasis: boosts higher frequencies (vocal tract / vocal cord
        # characteristics) relative to lower ones (room resonance, mic
        # rumble, background hum). Standard step in speech pipelines —
        # reduces how much a model can lean on "which room/mic this was
        # recorded in" instead of the actual voice.
        signal = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])

        return signal, sr


class FeatureExtractor:
    """Extracts a fixed-length MFCC feature vector from a raw audio signal."""

    def __init__(self, n_mfcc: int = N_MFCC, sample_rate: int = SAMPLE_RATE):
        self.n_mfcc = n_mfcc
        self.sample_rate = sample_rate

    def extract(self, signal: np.ndarray, sr: int) -> np.ndarray:
        import librosa

        mfcc = librosa.feature.mfcc(y=signal, sr=sr, n_mfcc=self.n_mfcc)
        # Drop coefficient 0 (overall frame energy/loudness) — we already
        # normalize volume in AudioLoader, so this coefficient mostly adds
        # recording-level noise rather than speaker/word information.
        mfcc = mfcc[1:, :]
        # Average over time so every clip -> one fixed-length vector,
        # regardless of how long the recording was.
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)
        return np.concatenate([mfcc_mean, mfcc_std])


class SoundFeaturePipeline:
    """Convenience wrapper: filepath in, feature vector out."""

    def __init__(self, loader: AudioLoader | None = None, extractor: FeatureExtractor | None = None):
        self.loader = loader or AudioLoader()
        self.extractor = extractor or FeatureExtractor()

    def extract_features(self, filepath: str) -> np.ndarray:
        signal, sr = self.loader.load(filepath)
        return self.extractor.extract(signal, sr)


# Module-level singleton + shortcut function, so anyone can just do:
#   from sounds import extract_features
#   vec = extract_features("some_recording.wav")
_default_pipeline = SoundFeaturePipeline()


def extract_features(filepath: str) -> np.ndarray:
    return _default_pipeline.extract_features(filepath)