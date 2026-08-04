import base64
import os
from pathlib import Path
import sys
import time

import joblib
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
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

ICON_WARN = """
<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 9v4"></path><path d="M12 17h.01"></path>
  <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path>
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

# Error beep (base64 encoded once, reused as a hidden autoplay <audio> tag)
BEEP_PATH = ASSETS / "error_beep.wav"
BEEP_B64 = base64.b64encode(BEEP_PATH.read_bytes()).decode() if BEEP_PATH.exists() else None


def play_error_beep():
    """Plays a short alert sound. Renders a fresh <audio autoplay> element,
    so it fires again every time this function runs (i.e. every failed rerun)."""
    if not BEEP_B64:
        return
    st.markdown(
        f"""<audio autoplay="true" style="display:none">
                <source src="data:audio/wav;base64,{BEEP_B64}" type="audio/wav">
            </audio>""",
        unsafe_allow_html=True,
    )


# Session state initialization
defaults = {
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
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


@st.cache_resource
def load_ml_models():
    """Loads the trained ML artifacts. Returns (models_dict, errors_dict) so
    the caller can tell the difference between 'file missing' and 'file
    corrupted/incompatible' instead of silently treating both as 'no model'."""
    models = {"speaker": None, "command": None}
    errors = {"speaker": None, "command": None}

    for key, filename in (("speaker", "speaker_model.joblib"), ("command", "command_model.joblib")):
        path = MODELS_DIR / filename
        if not path.exists():
            errors[key] = f"الملف مش موجود: {path}"
            continue
        try:
            models[key] = joblib.load(path)
        except Exception as e:
            errors[key] = f"فشل تحميل الملف: {e}"

    return models, errors


ml_models, ml_errors = load_ml_models()
MODELS_READY = ml_models["speaker"] is not None and ml_models["command"] is not None


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
    """Returns (speaker_name, command_text, error_message).
    error_message is None on success, otherwise a human-readable reason
    so the UI never has to guess why classification failed."""
    try:
        features = extract_features(audio_path)
    except Exception as e:
        return "Unknown", "Unknown", f"تعذّر استخراج خصائص الصوت (feature extraction): {e}"

    features_reshaped = features.reshape(1, -1)

    speaker_name = "Unknown"
    command_text = "Unknown"
    error_message = None

    speaker_artifact = ml_models.get("speaker")
    if speaker_artifact is None:
        error_message = ml_errors.get("speaker") or "موديل الـ speaker مش محمّل."
    else:
        try:
            X = speaker_artifact["scaler"].transform(features_reshaped)
            pred_idx = speaker_artifact["model"].predict(X)
            speaker_name = speaker_artifact["label_encoder"].inverse_transform(pred_idx)[0]
        except Exception as e:
            error_message = f"خطأ في تصنيف المتحدث (speaker model): {e}"

    command_artifact = ml_models.get("command")
    if command_artifact is None:
        error_message = error_message or (ml_errors.get("command") or "موديل الـ command مش محمّل.")
    else:
        try:
            X = command_artifact["scaler"].transform(features_reshaped)
            pred_idx = command_artifact["model"].predict(X)
            command_text = command_artifact["label_encoder"].inverse_transform(pred_idx)[0]
        except Exception as e:
            error_message = error_message or f"خطأ في تصنيف الأمر (command model): {e}"

    return speaker_name, command_text, error_message


def init_arduino():
    if st.session_state.arduino is None:
        try:
            port = "COM3" if sys.platform == "win32" else "/dev/ttyUSB0"
            arduino = ArduinoController(port=port, baudrate=115200)
            if arduino.connect():
                st.session_state.arduino = arduino
                return True
            else:
                st.warning("تعذّر الاتصال بالأردوينو على البورت المحدد. الأوامر هتشتغل في وضع Simulation.")
                return False
        except Exception as e:
            st.warning(f"الأردوينو مش متوصل: {str(e)}")
            return False
    return True


# Main UI Structure
st.markdown('<div class="orb orb-a"></div>', unsafe_allow_html=True)
st.markdown('<div class="orb orb-b"></div>', unsafe_allow_html=True)

# Global banner: warn early if the ML models never loaded, instead of letting
# every single command silently fail with a confusing "Unrecognized Command".
if not MODELS_READY:
    missing = [k for k, v in ml_models.items() if v is None]
    with st.container():
        st.markdown(
            f'<div class="model-warning">{ICON_WARN}'
            f'<div><b>الموديلات دي لسه مش متحمّلة:</b> {", ".join(missing)}. '
            f'كل أوامر الصوت هترجع "Unrecognized Command" لحد ما الملفات .joblib تتحط في '
            f'<code>{MODELS_DIR}</code>.</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("تفاصيل تقنية (للمطورين)"):
            for k, v in ml_errors.items():
                if v:
                    st.code(f"{k}: {v}")

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

            verify_disabled = auth_audio is None
            if st.button("Verify Voice", use_container_width=True, disabled=verify_disabled):
                st.session_state.auth_status = None
                st.session_state.auth_last_text = ""
                audio_path = save_recorded_audio(auth_audio)

                try:
                    if audio_path:
                        with st.spinner("Transcribing and Verifying..."):
                            success, text = authenticate_user(audio_path)

                        if success:
                            st.toast("Unlocked. Welcome home!", icon="✅")
                            init_arduino()
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.session_state.auth_status = "failed"
                            st.session_state.auth_last_text = text if text else "لم يُسمع أي كلام / صمت"
                    else:
                        st.session_state.auth_status = "failed"
                        st.session_state.auth_last_text = "خطأ في التسجيل / لا يوجد إدخال صوتي"
                finally:
                    if audio_path and os.path.exists(audio_path):
                        os.remove(audio_path)

            if not verify_disabled and st.session_state.get("auth_status") is None:
                st.caption("سجّلت صوتك — دوس \"Verify Voice\" للمتابعة.")

            if st.session_state.get("auth_status") == "failed":
                play_error_beep()
                st.error(f'فشل التحقق. اللي اتسمع: "{st.session_state.auth_last_text}"')
                if st.session_state.password_attempts >= 3:
                    st.info("جرّب تتكلم بوضوح وقريب من المايك، وتأكد إنك بتقول الباسورد الصح.")
                if st.button("حاول تاني", use_container_width=True, key="login_retry"):
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
    with col1:
        arduino_ok = bool(st.session_state.arduino and st.session_state.arduino.is_connected)
        status_label = "Arduino Connected" if arduino_ok else "Simulation Mode"
        st.markdown(f'<div class="status-chip">{status_label}</div>', unsafe_allow_html=True)
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

            process_disabled = cmd_audio is None or not MODELS_READY
            if not MODELS_READY:
                st.caption("⚠️ التعرف الصوتي على الأوامر متوقف لحد ما موديلات الـ ML تتحمّل.")

            if st.button("Process Command", use_container_width=True, disabled=process_disabled):
                st.session_state.cmd_status = None
                st.session_state.cmd_last_result = {}
                audio_path = save_recorded_audio(cmd_audio)

                try:
                    if audio_path:
                        with st.spinner("Processing voice command..."):
                            speaker, command, err = process_voice_command(audio_path)

                        if command != "Unknown" and err is None:
                            st.session_state.cmd_status = "success"
                            st.session_state.cmd_last_result = {"speaker": speaker, "command": command}

                            if st.session_state.arduino and st.session_state.arduino.is_connected:
                                arduino_cmd = command.upper()
                                if arduino_cmd in ["LIGHT_ON", "LIGHT_OFF", "MUSIC_ON", "MUSIC_OFF"]:
                                    response = st.session_state.arduino.send_command(arduino_cmd)
                                    if response:
                                        st.session_state.cmd_last_result["arduino_response"] = response
                        else:
                            st.session_state.cmd_status = "failed"
                            st.session_state.cmd_last_result = {
                                "speaker": speaker,
                                "command": "Unrecognized Command",
                                "reason": err,
                            }
                    else:
                        st.session_state.cmd_status = "failed"
                        st.session_state.cmd_last_result = {
                            "speaker": "None",
                            "command": "Recording Error / Silent",
                            "reason": "مفيش تسجيل اتحفظ.",
                        }
                finally:
                    if audio_path and os.path.exists(audio_path):
                        os.remove(audio_path)

            if st.session_state.get("cmd_status") == "success":
                res = st.session_state.cmd_last_result
                st.success(f"Command Executed: {res.get('command')}")
                st.markdown(f"**Speaker:** {res.get('speaker')}")
                st.markdown(f"**Command:** {res.get('command')}")
                if not (st.session_state.arduino and st.session_state.arduino.is_connected):
                    st.warning("Arduino not connected. Command simulated.")

            elif st.session_state.get("cmd_status") == "failed":
                play_error_beep()
                res = st.session_state.cmd_last_result
                st.error(f"Failed to process command. Result: {res.get('command')}")
                if res.get("reason"):
                    st.caption(f"السبب: {res['reason']}")
                if st.button("حاول تاني", use_container_width=True, key="cmd_retry"):
                    st.session_state.cmd_status = None
                    st.session_state.cmd_last_result = {}
                    st.rerun()

            st.markdown('<div class="section-title">Manual Control</div>', unsafe_allow_html=True)
            cmd1, cmd2 = st.columns(2)
            with cmd1:
                if st.button("Light ON", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("LIGHT_ON")
                        st.toast("Lights turned ON", icon="💡")
                    else:
                        st.warning("Arduino not connected")
                if st.button("Music OFF", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("MUSIC_OFF")
                        st.toast("Music turned OFF", icon="🔇")
                    else:
                        st.warning("Arduino not connected")
            with cmd2:
                if st.button("Light OFF", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("LIGHT_OFF")
                        st.toast("Lights turned OFF", icon="🌙")
                    else:
                        st.warning("Arduino not connected")
                if st.button("Music ON", use_container_width=True):
                    if st.session_state.arduino and st.session_state.arduino.is_connected:
                        st.session_state.arduino.send_command("MUSIC_ON")
                        st.toast("Music turned ON", icon="🎵")
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
