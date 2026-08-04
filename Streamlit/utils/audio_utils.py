"""
Audio utilities for the Streamlit smart-home app.

Recording happens in the user's BROWSER via st.audio_input (built into
Streamlit >= 1.36 — no extra package needed). This is required because
Streamlit Community Cloud servers have no physical microphone, so
pyaudio/sounddevice (which need direct hardware access) can never work
there. The browser records the audio and streamlit sends us the bytes.
"""

import tempfile

import librosa
import numpy as np

SAMPLE_RATE = 16000
N_MFCC = 40


def save_recorded_audio(audio_value) -> str | None:
    """
    Save the audio returned by st.audio_input to a temporary .wav file.

    Parameters
    ----------
    audio_value : UploadedFile | None
        The object returned by st.audio_input(). None if the user hasn't
        recorded anything yet.

    Returns
    -------
    str | None
        Path to the saved temp .wav file, or None if there was no audio.
    """
    if audio_value is None:
        return None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(audio_value.getvalue())
    tmp.close()
    return tmp.name


def extract_features(filepath: str) -> np.ndarray:
    """
    Extract a fixed-length MFCC feature vector (mean + std across time)
    from a .wav file. This mirrors the exact feature pipeline used in
    ML/Model/sounds.py to train speaker_model.pkl and command_model.pkl,
    so predictions stay consistent.
    """
    signal, sr = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    mfcc = librosa.feature.mfcc(y=signal, sr=sr, n_mfcc=N_MFCC)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    return np.concatenate([mfcc_mean, mfcc_std])
