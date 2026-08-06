import base64
import os
from pathlib import Path
import sys
import time
import joblib
import streamlit as st
from utils.arduino_utils import ArduinoController
from utils.audio_utils import extract_features, save_recorded_audio
from utils.stt_utils import transcribe_audio





st.set_page_config(
    page_title="Smart Home",
    page_icon="house",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Paths configuration
ASSETS = Path(__file__).parent / "assets"
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "ML" / "Model" / "artifacts"

sys.path.append(str(BASE_DIR / "ML"))
sys.path.append(str(BASE_DIR / "ML" / "Model"))
MUSIC_FILE = Path(__file__).parent / "audio" / "music.mp3"

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

# Load background styles
img_path = ASSETS / "home.png"
if img_path.exists():
    b64 = base64.b64encode(img_path.read_bytes()).decode()
    bg_css = f"url('data:image/png;base64,{b64}')"
else:
    bg_css = "linear-gradient(135deg,#111827,#1e293b)"

css_path = ASSETS / "style.css"
if css_path.exists():
    css = css_path.read_text(encoding="utf-8").replace("__BG_IMAGE__", bg_css)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# Session state initialization
if "recording" not in st.session_state:
    st.session_state.recording = False
if "unlocked" not in st.session_state:
    st.session_state.unlocked = False
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "login"
if "arduino" not in st.session_state:
    st.session_state.arduino = None
if "password_attempts" not in st.session_state:
    st.session_state.password_attempts = 0

if "auth_status" not in st.session_state:
    st.session_state.auth_status = None
if "auth_last_text" not in st.session_state:
    st.session_state.auth_last_text = ""
if "cmd_status" not in st.session_state:
    st.session_state.cmd_status = None
if "cmd_last_result" not in st.session_state:
    st.session_state.cmd_last_result = {}
if "play_music" not in st.session_state:
    st.session_state.play_music = False


@st.cache_resource
def load_ml_models():
    models = {"speaker": None, "command": None}

    print("=" * 50)
    print("Loading ML Models...")

    speaker_path = MODELS_DIR / "speaker_model.joblib"
    command_path = MODELS_DIR / "command_model.joblib"

    print("Speaker path:", speaker_path)
    print("Speaker exists:", speaker_path.exists())

    print("Command path:", command_path)
    print("Command exists:", command_path.exists())

    if speaker_path.exists():
        try:
            models["speaker"] = joblib.load(speaker_path)
            print("✅ Speaker model loaded.")
            print(models["speaker"].keys())
        except Exception as e:
            print("Speaker loading failed:", e)

    if command_path.exists():
        try:
            models["command"] = joblib.load(command_path)
            print("✅ Command model loaded.")
            print(models["command"].keys())
        except Exception as e:
            print("Command loading failed:", e)

    return models


for p in sys.path:
    st.write(p)

ml_models = load_ml_models()

st.sidebar.write("## Debug")

st.sidebar.write("Speaker loaded:", ml_models["speaker"] is not None)
st.sidebar.write("Command loaded:", ml_models["command"] is not None)

def authenticate_user(audio_path):
    text = transcribe_audio(audio_path)
    expected_password = "esp32"
    clean_text = str(text).strip().lower()
    if expected_password == clean_text and clean_text != "":
        st.session_state.authenticated = True
        st.session_state.unlocked = True
        st.session_state.current_page = "dashboard"
        return True, text
    else:
        st.session_state.password_attempts += 1
        return False, text

#here the command model should work
def process_voice_command(audio_path):
    features = extract_features(audio_path)
    print("=" * 50)
    print("Feature shape:", features.shape)
    print("First 10 values:")
    print(features[:10])

    if features is None:
        return "Unknown", "Unknown"

    features_reshaped = features.reshape(1, -1)

    speaker_name = "Unknown"
    speaker_artifact = ml_models.get('speaker')
    if speaker_artifact is not None:
        try:
            X = speaker_artifact['scaler'].transform(features_reshaped)
            pred_idx = speaker_artifact['model'].predict(X)

            speaker_name = speaker_artifact['label_encoder'].inverse_transform(pred_idx)[0]
        except Exception as e:
            print(f"Speaker prediction error: {e}")

    command_text = "Unknown"
    command_artifact = ml_models.get('command')
    if command_artifact is not None:
        try:
            X = command_artifact['scaler'].transform(features_reshaped)
            pred_idx = command_artifact['model'].predict(X)
            print("Predicted index:", pred_idx)

            print(
                "Classes:",
                command_artifact["label_encoder"].classes_
            )

            print(
                "Prediction:",
                command_artifact["label_encoder"].inverse_transform(pred_idx)
            )
            command_text = command_artifact['label_encoder'].inverse_transform(pred_idx)[0]
        except Exception as e:
            print(f"Command prediction error: {e}")

    return speaker_name, command_text


def init_arduino():
    if st.session_state.arduino is None:
        try:
            port = 'COM3' if sys.platform == 'win32' else '/dev/ttyUSB0'
            arduino = ArduinoController(port=port, baudrate=115200)
            if arduino.connect():
                arduino.authenticate("esp32")
                st.session_state.arduino = arduino
                return True
            else:
                st.warning("ESP32 Connection failed.")
                return False
        except Exception as e:
            st.warning(f"ESP32 not connected: {str(e)}")
            return False
    return True


# Main UI Structure
st.markdown('<div class="orb orb-a"></div>', unsafe_allow_html=True)
st.markdown('<div class="orb orb-b"></div>', unsafe_allow_html=True)

# Login Page
if st.session_state.current_page == "login":
    st.markdown(
        '<div class="header-container">'
        '<div class="eyebrow-row"><div class="badge"><span class="dot"></span>Voice Controlled Access</div></div>'
        '<div class="title">Smart Home</div>'
        '<div class="subtitle">Say your passphrase to unlock the front door.</div>'
        '</div>',
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
                else:
                    st.session_state.auth_status = "failed"
                    st.session_state.auth_last_text = "Recording error / No input"

            if st.session_state.get("auth_status") == "failed":
                st.error(f'Authentication failed. Heard: "{st.session_state.auth_last_text}"')
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
        '</div>',
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
            st.session_state.play_music = False
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

            cmd_audio = st.audio_input("Speak your command", key="cmd_audio_input")

            if cmd_audio is not None and st.button("Process Command", use_container_width=True):
                st.session_state.cmd_status = None
                st.session_state.cmd_last_result = {}
                audio_path = save_recorded_audio(cmd_audio)

                if audio_path:
                    with st.spinner("Processing voice command..."):
                        speaker, raw_command = process_voice_command(audio_path)

                    if os.path.exists(audio_path):
                        os.remove(audio_path)

                    clean_cmd = str(raw_command).strip().lower()
                    valid_commands = ["light_on", "light_off", "music_on", "music_off"]

                    if clean_cmd in valid_commands:
                        display_cmd = clean_cmd.replace("_", " ").upper()
                        st.session_state.cmd_status = "success"
                        st.session_state.cmd_last_result = {
                            "speaker": speaker,
                            "command": display_cmd,
                            "raw_detected": clean_cmd
                        }

                        if clean_cmd == "music_on":
                            st.session_state.play_music = True
                        elif clean_cmd == "music_off":
                            st.session_state.play_music = False

                        if st.session_state.arduino and st.session_state.arduino.is_connected:
                            response = st.session_state.arduino.send_command(clean_cmd)
                            if response:
                                st.session_state.cmd_last_result["arduino_response"] = response
                    else:
                        st.session_state.cmd_status = "failed"
                        st.session_state.cmd_last_result = {
                            "speaker": speaker,
                            "raw_detected": raw_command if raw_command != "Unknown" else "Unrecognized Audio / Noise",
                            "command": "Unrecognized Command"
                        }
                else:
                    st.session_state.cmd_status = "failed"
                    st.session_state.cmd_last_result = {"speaker": "None", "raw_detected": "Audio Recording Error",
                                                        "command": "Recording Error / Silent"}

            if st.session_state.get("cmd_status") == "success":
                res = st.session_state.cmd_last_result
                st.success(f"Command Executed: {res.get('command')}")
                st.info(f"System Heard: '{res.get('raw_detected')}'")
                st.markdown(f"**Speaker:** {res.get('speaker')}")
                if not (st.session_state.arduino and st.session_state.arduino.is_connected):
                    st.warning("Arduino not connected. Command simulated.")

            elif st.session_state.get("cmd_status") == "failed":
                res = st.session_state.cmd_last_result
                st.error(f"Failed to process command. System Heard: '{res.get('raw_detected')}'")
                if st.button("Try Again", use_container_width=True, key="cmd_retry"):
                    st.session_state.cmd_status = None
                    st.session_state.cmd_last_result = {}
                    st.rerun()

            # Audio Player Feature
            if st.session_state.play_music:
                st.markdown('<div class="section-title">Playing Music</div>', unsafe_allow_html=True)
                if MUSIC_FILE.exists():
                    st.audio(str(MUSIC_FILE), autoplay=True)
                else:
                    st.warning("Music file not found in path: Streamlit/audio/music.mp3")

            st.markdown('<div class="section-title">Manual Control</div>', unsafe_allow_html=True)
            cmd1, cmd2 = st.columns(2)
            with cmd1:
                if st.button("Light ON", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("light_on")
                        st.success("Lights turned ON")
                    else:
                        st.warning("Arduino not connected")

                if st.button("Music OFF", use_container_width=True):
                    st.session_state.play_music = False
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("music_off")
                        st.success("Music turned OFF")
                    else:
                        st.warning("Arduino not connected")
                    st.rerun()

            with cmd2:
                if st.button("Light OFF", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("light_off")
                        st.success("Lights turned OFF")
                    else:
                        st.warning("Arduino not connected")

                if st.button("Music ON", use_container_width=True):
                    st.session_state.play_music = True
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("music_on")
                        st.success("Music turned ON")
                    else:
                        st.warning("Arduino not connected")
                    st.rerun()

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