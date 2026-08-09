
import tempfile

import librosa
import numpy as np

SAMPLE_RATE = 16000
N_MFCC = 40

_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"


def _bytes_are_webm(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == _WEBM_MAGIC


def _transcode_to_wav(data: bytes) -> bytes:
    import av
    import io

    src = io.BytesIO(data)
    out = io.BytesIO()

    with av.open(src) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        with av.open(out, mode="w", format="wav") as out_container:
            out_stream = out_container.add_stream("pcm_s16le", rate=SAMPLE_RATE)
            out_stream.layout = "mono"

            for frame in container.decode(stream):
                for resampled in resampler.resample(frame):
                    for packet in out_stream.encode(resampled):
                        out_container.mux(packet)
            for resampled in resampler.resample(None):
                for packet in out_stream.encode(resampled):
                    out_container.mux(packet)
            for packet in out_stream.encode(None):
                out_container.mux(packet)

    return out.getvalue()


def save_recorded_audio(audio_value) -> str | None:

    if audio_value is None:
        return None

    data = audio_value.getvalue()
    if _bytes_are_webm(data):
        data = _transcode_to_wav(data)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(data)
    tmp.close()
    return tmp.name


def extract_features(filepath: str) -> np.ndarray:

    signal, sr = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    mfcc = librosa.feature.mfcc(y=signal, sr=sr, n_mfcc=N_MFCC)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    return np.concatenate([mfcc_mean, mfcc_std])
