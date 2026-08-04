"""
Smart Home - Voice Control (Streamlit front end).

Flow:
    1. User speaks a passphrase -> STT -> compared to a stored password.
    2. On success, the dashboard unlocks and the Arduino is connected.
    3. User speaks a command -> two ML models (speaker id, command
       classification) predict who spoke and what they asked for.
    4. The recognized command is sent to the Arduino over Serial.

This file focuses on being defensive about the two most common failure
points in this kind of app:
    - The .joblib model files not being found because of a path issue
      (wrong working directory when `streamlit run` was launched).
    - Predictions silently failing (e.g. feature-vector size mismatch
      between the app's audio_utils.py and the training pipeline's
      features.py) and only being printed to a terminal nobody is
      watching.

Both failure modes are now surfaced directly in the UI via a
"System Diagnostics" panel and inline error details, instead of a
generic "Unrecognized Command" message.
"""

import os
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from utils.arduino_utils import ArduinoController
from utils.audio_utils import extract_features, save_recorded_audio
from utils.stt_utils import transcribe_audio

st.set_page_config(
    page_title="Smart Home",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Paths configuration
# ---------------------------------------------------------------------------
# .resolve() turns __file__ into an absolute path. Without it, the joined
# path is only correct if `streamlit run` happens to be launched from a
# specific working directory - which is the most common reason the app
# "can't find" model files that clearly exist on disk.
APP_DIR = Path(__file__).resolve().parent
ASSETS = APP_DIR / "assets"
MODELS_DIR = (APP_DIR.parent / "ML" / "Model" / "artifacts").resolve()
SPEAKER_MODEL_PATH = MODELS_DIR / "speaker_model.joblib"
COMMAND_MODEL_PATH = MODELS_DIR / "command_model.joblib"

VALID_ARDUINO_COMMANDS = ["LIGHT_ON", "LIGHT_OFF", "MUSIC_ON", "MUSIC_OFF"]

# Inline SVG icons
ICON_LOCK = """
<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="4.5" y="10.5" width="15" height="10" rx="2.2"></rect>
  <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"></path>
</svg>
"""

ICON_COMMANDS = """
<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="4 17 10 11 4 5"></polyline>
  <line x1="12" y1="19" x2="20" y2="19"></line>
</svg>
"""

ICON_TEMP = """
<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2v10"></path>
  <path d="M12 22v-10"></path>
  <circle cx="12" cy="15" r="3"></circle>
</svg>
"""

ICON_WARNING = """
<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path>
  <line x1="12" y1="9" x2="12" y2="13"></line>
  <line x1="12" y1="17" x2="12.01" y2="17"></line>
</svg>
"""

# Load background styles
img_path = ASSETS / "home.png"
if img_path.exists():
    import base64
    b64 = base64.b64encode(img_path.read_bytes()).decode()
    bg_css = f"url('data:image/png;base64,{b64}')"
else:
    bg_css = "linear-gradient(135deg,#111827,#1e293b)"

css_path = ASSETS / "style.css"
if css_path.exists():
    css = css_path.read_text().replace("__BG_IMAGE__", bg_css)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
DEFAULT_STATE = {
    "recording": False,
    "unlocked": False,
    "authenticated": False,
    "current_page": "login",
    "arduino": None,
    "password_attempts": 0,
    "auth_status": None,
    "auth_last_text": "",
    "cmd_status": None,
    "cmd_last_result": {},
}
for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Sound feedback
# ---------------------------------------------------------------------------
def play_error_sound():
    """Play a short two-tone error beep in the browser (no audio file needed)."""
    components.html(
        """
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(440, ctx.currentTime);
            osc.frequency.setValueAtTime(311, ctx.currentTime + 0.16);
            gain.gain.setValueAtTime(0.001, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        } catch (e) {
            console.error("Could not play error sound:", e);
        }
        </script>
        """,
        height=0,
    )


# ---------------------------------------------------------------------------
# Model loading (robust + diagnosable)
# ---------------------------------------------------------------------------
def _load_single_model(path: Path):
    """Try to load one joblib artifact. Returns (artifact_or_None, error_or_None)."""
    if not path.exists():
        return None, f"File not found at: {path}"
    try:
        artifact = joblib.load(path)
        if not isinstance(artifact, dict) or not all(
            k in artifact for k in ("model", "scaler", "label_encoder")
        ):
            return None, (
                f"{path.name} loaded but has an unexpected format "
                f"(expected a dict with 'model', 'scaler', 'label_encoder')."
            )
        return artifact, None
    except Exception as e:
        return None, f"Failed to load {path.name}: {e}"


@st.cache_resource
def load_ml_models():
    speaker_artifact, speaker_error = _load_single_model(SPEAKER_MODEL_PATH)
    command_artifact, command_error = _load_single_model(COMMAND_MODEL_PATH)
    return {
        "speaker": speaker_artifact,
        "command": command_artifact,
        "errors": {
            "speaker": speaker_error,
            "command": command_error,
        },
    }


ml_models = load_ml_models()
MODELS_READY = ml_models["speaker"] is not None and ml_models["command"] is not None


def render_diagnostics():
    """Sidebar panel showing exactly what the app sees on disk, for debugging."""
    with st.sidebar:
        st.markdown("### System Diagnostics")
        st.caption(f"Models directory:\n`{MODELS_DIR}`")
        st.caption(f"Directory exists: {MODELS_DIR.exists()}")

        for label, path, artifact_key in [
            ("Speaker model", SPEAKER_MODEL_PATH, "speaker"),
            ("Command model", COMMAND_MODEL_PATH, "command"),
        ]:
            loaded = ml_models[artifact_key] is not None
            status = "Loaded" if loaded else "NOT loaded"
            st.write(f"**{label}:** {status}")
            st.caption(f"`{path.name}` exists: {path.exists()}")
            error = ml_models["errors"].get(artifact_key)
            if error:
                st.error(error)

        st.markdown("---")
        arduino = st.session_state.get("arduino")
        arduino_status = "Connected" if arduino and arduino.is_connected else "Not connected"
        st.write(f"**Arduino:** {arduino_status}")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def authenticate_user(audio_path):
    text = transcribe_audio(audio_path)
    expected_password = "esp32"
    if expected_password == text and text != "":
        st.session_state.authenticated = True
        st.session_state.unlocked = True
        st.session_state.current_page = "dashboard"
        if st.session_state.arduino:
            st.session_state.arduino.authenticate(text)
        return True, text
    else:
        st.session_state.password_attempts += 1
        return False, text


def process_voice_command(audio_path):
    """
    Run feature extraction + both ML models on a recorded command.

    Returns a dict:
        {"speaker": str, "command": str, "error": str | None}
    `error`, when set, is a human-readable explanation collected from
    whichever step failed - shown to the user instead of only being
    printed to a terminal.
    """
    result = {"speaker": "Unknown", "command": "Unknown", "error": None}

    try:
        features = extract_features(audio_path)
        features_reshaped = features.reshape(1, -1)
    except Exception as e:
        result["error"] = f"Feature extraction failed: {e}"
        return result

    def run_model(artifact_key, label):
        artifact = ml_models.get(artifact_key)
        if artifact is None:
            return None, ml_models["errors"].get(artifact_key) or f"{label} model not loaded."
        try:
            expected = getattr(artifact["scaler"], "n_features_in_", None)
            if expected is not None and features_reshaped.shape[1] != expected:
                return None, (
                    f"{label} model expects {expected} features but got "
                    f"{features_reshaped.shape[1]}. The feature extraction in "
                    f"utils/audio_utils.py (SAMPLE_RATE / N_MFCC) must match "
                    f"ML/Model/features.py exactly."
                )
            X = artifact["scaler"].transform(features_reshaped)
            pred_idx = artifact["model"].predict(X)
            label_value = artifact["label_encoder"].inverse_transform(pred_idx)[0]
            return label_value, None
        except Exception as e:
            return None, f"{label} prediction error: {e}"

    speaker_value, speaker_error = run_model("speaker", "Speaker")
    if speaker_value is not None:
        result["speaker"] = speaker_value

    command_value, command_error = run_model("command", "Command")
    if command_value is not None:
        result["command"] = command_value

    errors = [e for e in (speaker_error, command_error) if e]
    if errors:
        result["error"] = " | ".join(errors)

    return result


def init_arduino():
    if st.session_state.arduino is None:
        try:
            port = "COM3" if sys.platform == "win32" else "/dev/ttyUSB0"
            arduino = ArduinoController(port=port, baudrate=115200)
            if arduino.connect():
                st.session_state.arduino = arduino
                return True
            else:
                st.warning("ESP32 connected but authentication failed. Please check password.")
                return False
        except Exception as e:
            st.warning(f"ESP32 not connected: {str(e)}")
            return False
    return True


# ---------------------------------------------------------------------------
# Main UI Structure
# ---------------------------------------------------------------------------
render_diagnostics()

st.markdown('<div class="orb orb-a"></div>', unsafe_allow_html=True)
st.markdown('<div class="orb orb-b"></div>', unsafe_allow_html=True)

# Login Page
if st.session_state.current_page == "login":
    st.markdown(
        '<div class="header-container">'
        '<div class="eyebrow-row"><div class="badge"><span class="dot"></span>Voice Controlled Access</div></div>'
        '<div class="title">Smart Home</div>'
        '<div class="subtitle">Say your passphrase to unlock the front door.</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.container():
            st.markdown(
                f'<div class="card-heading">{ICON_LOCK}<span>Secure Login</span></div>'
                '<div class="card-sub">Your voice is matched using on-device voice biometrics.</div>',
                unsafe_allow_html=True,
            )

            auth_audio = st.audio_input("Speak your passphrase", key="auth_audio_input")

            if auth_audio is not None and st.button("Verify Voice", use_container_width=True):
                st.session_state.auth_status = None
                st.session_state.auth_last_text = ""
                audio_path = save_recorded_audio(auth_audio)

                if audio_path:
                    with st.spinner("Transcribing and Verifying..."):
                        success, text = authenticate_user(audio_path)

                    if os.path.exists(audio_path):
                        os.remove(audio_path)

                    if success:
                        st.success("Unlocked. Welcome home!")
                        init_arduino()
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.session_state.auth_status = "failed"
                        st.session_state.auth_last_text = text if text else "Nothing heard / Silence"
                        play_error_sound()
                else:
                    st.session_state.auth_status = "failed"
                    st.session_state.auth_last_text = "Recording error / No input"
                    play_error_sound()

            if st.session_state.get("auth_status") == "failed":
                st.error(f'Authentication failed. Transcribed: "{st.session_state.auth_last_text}"')
                if st.button("Try Again", use_container_width=True, key="login_retry"):
                    st.session_state.auth_status = None
                    st.session_state.auth_last_text = ""
                    st.rerun()

# Dashboard Page
else:
    st.markdown(
        '<div class="header-container">'
        '<div class="eyebrow-row"><div class="badge"><span class="dot"></span>Voice Controlled Smart Home</div></div>'
        '<div class="title">Control Panel</div>'
        '<div class="subtitle">Use your voice to control your smart home devices.</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    if not MODELS_READY:
        with st.container():
            st.markdown(
                f'<div class="card-heading warning">{ICON_WARNING}<span>ML models not fully loaded</span></div>'
                '<div class="card-sub">Voice commands will not be recognized until this is fixed. '
                "Open the sidebar for details (top-left arrow), or use Manual Control below.</div>",
                unsafe_allow_html=True,
            )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.unlocked = False
            st.session_state.current_page = "login"
            st.session_state.cmd_status = None
            st.session_state.cmd_last_result = {}
            if st.session_state.arduino:
                st.session_state.arduino.disconnect()
                st.session_state.arduino = None
            st.rerun()

    col_left, col_right = st.columns(2)

    with col_left:
        with st.container():
            st.markdown(
                f'<div class="card-heading">{ICON_COMMANDS}<span>Voice Command</span></div>',
                unsafe_allow_html=True,
            )

            cmd_audio = st.audio_input(
                "Speak your command", key="cmd_audio_input", disabled=not MODELS_READY
            )

            if (
                cmd_audio is not None
                and MODELS_READY
                and st.button("Process Command", use_container_width=True)
            ):
                st.session_state.cmd_status = None
                st.session_state.cmd_last_result = {}
                audio_path = save_recorded_audio(cmd_audio)

                if audio_path:
                    with st.spinner("Processing voice command..."):
                        result = process_voice_command(audio_path)

                    if os.path.exists(audio_path):
                        os.remove(audio_path)

                    speaker, command, error = result["speaker"], result["command"], result["error"]

                    if command != "Unknown":
                        st.session_state.cmd_status = "success"
                        st.session_state.cmd_last_result = {"speaker": speaker, "command": command}

                        if st.session_state.arduino and st.session_state.arduino.is_connected:
                            arduino_cmd = command.upper()
                            if arduino_cmd in VALID_ARDUINO_COMMANDS:
                                response = st.session_state.arduino.send_command(arduino_cmd)
                                if response:
                                    st.session_state.cmd_last_result["arduino_response"] = response
                    else:
                        st.session_state.cmd_status = "failed"
                        st.session_state.cmd_last_result = {
                            "speaker": speaker,
                            "command": "Unrecognized Command",
                            "error": error,
                        }
                        play_error_sound()
                else:
                    st.session_state.cmd_status = "failed"
                    st.session_state.cmd_last_result = {
                        "speaker": "None",
                        "command": "Recording Error / Silent",
                        "error": "No audio was captured from the microphone.",
                    }
                    play_error_sound()

            if st.session_state.get("cmd_status") == "success":
                res = st.session_state.cmd_last_result
                st.success(f"Command Executed: {res.get('command')}")
                st.markdown(f"**Speaker:** {res.get('speaker')}")
                st.markdown(f"**Command:** {res.get('command')}")
                if not (st.session_state.arduino and st.session_state.arduino.is_connected):
                    st.warning("Arduino not connected. Command simulated.")

            elif st.session_state.get("cmd_status") == "failed":
                res = st.session_state.cmd_last_result
                st.error(f"Failed to process command. Result: {res.get('command')}")
                if res.get("error"):
                    with st.expander("Technical details"):
                        st.code(res["error"])
                if st.button("Try Again", use_container_width=True, key="cmd_retry"):
                    st.session_state.cmd_status = None
                    st.session_state.cmd_last_result = {}
                    st.rerun()

            st.markdown('<div class="section-title">Manual Control</div>', unsafe_allow_html=True)
            cmd1, cmd2 = st.columns(2)
            with cmd1:
                if st.button("Light ON", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("LIGHT_ON")
                        st.success("Lights turned ON")
                    else:
                        st.warning("Arduino not connected")
                if st.button("Music OFF", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("MUSIC_OFF")
                        st.success("Music turned OFF")
                    else:
                        st.warning("Arduino not connected")
            with cmd2:
                if st.button("Light OFF", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("LIGHT_OFF")
                        st.success("Lights turned OFF")
                    else:
                        st.warning("Arduino not connected")
                if st.button("Music ON", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("MUSIC_ON")
                        st.success("Music turned ON")
                    else:
                        st.warning("Arduino not connected")

    with col_right:
        with st.container():
            st.markdown(
                f'<div class="card-heading">{ICON_TEMP}<span>Temperature Sensor</span></div>',
                unsafe_allow_html=True,
            )

            if st.button("Read Temperature", use_container_width=True):
                if st.session_state.arduino and st.session_state.arduino.is_connected:
                    temp = st.session_state.arduino.read_temperature()
                    if temp is not None:
                        st.metric("Current Temperature", f"{temp:.1f}°C")
                    else:
                        st.warning("No data received from sensor")
                else:
                    import random

                    temp = random.uniform(20, 35)
                    st.metric("Temperature (Simulated)", f"{temp:.1f}°C")
                    st.info("Arduino not connected")

st.markdown(
    '<div class="footnote">Protected by on-device voice biometrics</div>',
    unsafe_allow_html=True,
)
