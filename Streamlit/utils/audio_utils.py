
import tempfile

import librosa
import numpy as np

SAMPLE_RATE = 16000
N_MFCC = 40


def save_recorded_audio(audio_value) -> str | None:

    if audio_value is None:
        return None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(audio_value.getvalue())
    tmp.close()
    return tmp.name


def extract_features(filepath: str) -> np.ndarray:

    signal, sr = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    mfcc = librosa.feature.mfcc(y=signal, sr=sr, n_mfcc=N_MFCC)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    return np.concatenate([mfcc_mean, mfcc_std])
