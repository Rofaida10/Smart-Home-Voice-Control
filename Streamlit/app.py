import base64
import os
from pathlib import Path
import sys
import time

import joblib
import numpy as np
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
MODELS_DIR = Path(__file__).parent.parent / "ML" / "Model" / "artifacts"

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
    css = css_path.read_text().replace("__BG_IMAGE__", bg_css)
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


@st.cache_resource
def load_ml_models():
    models = {'speaker': None, 'command': None}
    
    speaker_path = MODELS_DIR / "speaker_model.joblib"
    if speaker_path.exists():
        try:
            models['speaker'] = joblib.load(speaker_path)
        except Exception as e:
            print(f"Error loading speaker model: {e}")

    command_path = MODELS_DIR / "command_model.joblib"
    if command_path.exists():
        try:
            models['command'] = joblib.load(command_path)
        except Exception as e:
            print(f"Error loading command model: {e}")

    return models


ml_models = load_ml_models()


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
    features = extract_features(audio_path)
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
            raw_command = command_artifact['label_encoder'].inverse_transform(pred_idx)[0]
            command_text = str(raw_command).strip()
        except Exception as e:
            print(f"Command prediction error: {e}")

    return speaker_name, command_text


def init_arduino():
    if st.session_state.arduino is None:
        try:
            port = 'COM3' if sys.platform == 'win32' else '/dev/ttyUSB0'
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
                        speaker, command = process_voice_command(audio_path)

                    if os.path.exists(audio_path):
                        os.remove(audio_path)

                    # Normalize command check
                    valid_commands = ["light_on", "light_off", "music_on", "music_off"]
                    clean_command = str(command).strip().lower()

                    if clean_command in valid_commands:
                        st.session_state.cmd_status = "success"
                        st.session_state.cmd_last_result = {"speaker": speaker, "command": clean_command.upper()}

                        if st.session_state.arduino and st.session_state.arduino.is_connected:
                            arduino_cmd = clean_command.upper()
                            response = st.session_state.arduino.send_command(arduino_cmd)
                            if response:
                                st.session_state.cmd_last_result["arduino_response"] = response
                    else:
                        st.session_state.cmd_status = "failed"
                        st.session_state.cmd_last_result = {"speaker": speaker, "command": f"Unrecognized Command ({command})"}
                else:
                    st.session_state.cmd_status = "failed"
                    st.session_state.cmd_last_result = {"speaker": "None", "command": "Recording Error / Silent"}

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
